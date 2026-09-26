from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import oracle

from backend.app.models import Team, TeamMember
from backend.app.routes import teams as teams_route
from backend.app.services.spaces import SpaceContext


_SPACE = SpaceContext(
    space_id="concurrency-review-space",
    space_name="Concurrency Review Space",
    is_global_admin=False,
    space_role="space_admin",
)


def _seed_team(db_sessionmaker) -> str:
    with db_sessionmaker() as session:
        team = Team(space_id=_SPACE.space_id, name="Capacity Concurrency Team")
        session.add(team)
        session.commit()
        return team.team_id


def test_oracle_team_capacity_lock_is_scoped_and_has_no_row_limit(db_sessionmaker):
    team_id = _seed_team(db_sessionmaker)
    orm_statements = []
    executed_sql = []

    def capture_orm_statement(state):
        if state.is_select:
            orm_statements.append(state.statement)

    def capture_sql(_connection, _cursor, statement, _parameters, _context, _executemany):
        executed_sql.append(" ".join(statement.upper().split()))

    engine = db_sessionmaker.kw["bind"]
    with db_sessionmaker() as session:
        session.autoflush = True
        session.add(
            TeamMember(
                space_id=_SPACE.space_id,
                team_id=team_id,
                member_name="Pending member must not flush",
                role="member",
                hours_capacity=5,
            )
        )
        event.listen(session, "do_orm_execute", capture_orm_statement)
        event.listen(engine, "before_cursor_execute", capture_sql)
        try:
            teams_route._lock_active_team(session, team_id, _SPACE)
        finally:
            event.remove(session, "do_orm_execute", capture_orm_statement)
            event.remove(engine, "before_cursor_execute", capture_sql)
        session.rollback()

    assert len(orm_statements) == 1
    assert executed_sql and executed_sql[0].startswith("SELECT")
    assert not any(sql.startswith("INSERT") for sql in executed_sql)
    sql = str(orm_statements[0].compile(dialect=oracle.dialect())).upper()
    table = Team.__tablename__.upper()

    assert "FOR UPDATE" in sql
    assert f'"{table}".SPACE_ID' in sql
    assert f'"{table}".TEAM_ID' in sql
    assert f'"{table}".DELETED_AT IS NULL' in sql
    assert "FETCH" not in sql
    assert "FIRST" not in sql
    assert "ROWNUM" not in sql


@pytest.mark.anyio
async def test_delete_team_locks_team_before_member_updates_on_sqlite(client, db_sessionmaker):
    team_response = await client.post(
        "/project-manager/api/teams",
        json={"name": "Delete Lock Order Team"},
    )
    assert team_response.status_code == 201, team_response.text
    team_id = team_response.json()["team_id"]
    statements = []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(" ".join(statement.upper().split()))

    engine = db_sessionmaker.kw["bind"]
    if engine.dialect.name != "sqlite":
        pytest.skip("Statement order here is a SQLite proxy, not a live Oracle test")

    event.listen(engine, "before_cursor_execute", capture)
    try:
        member_response = await client.post(
            f"/project-manager/api/teams/{team_id}/members",
            json={"member_name": "Member", "hours_capacity": 20},
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert member_response.status_code == 201, member_response.text
    assert statements, "No SQL captured during member creation"

    team_table = Team.__tablename__.upper()
    member_table = TeamMember.__tablename__.upper()
    team_lock_select = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith("SELECT")
        and f'FROM "{team_table}"' in sql
        and f'"{team_table}".SPACE_ID' in sql
        and f'"{team_table}".DELETED_AT IS NULL' in sql
    )
    member_insert = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith(f'INSERT INTO "{member_table}"')
    )
    aggregate_select = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith("SELECT")
        and "SUM(" in sql
        and f'"{member_table}"' in sql
    )
    capacity_update = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith(f'UPDATE "{team_table}"')
    )
    assert team_lock_select < member_insert < aggregate_select < capacity_update

    statements.clear()
    event.listen(engine, "before_cursor_execute", capture)
    try:
        deleted = await client.delete(f"/project-manager/api/teams/{team_id}")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert deleted.status_code == 204, deleted.text
    team_lock_select = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith("SELECT")
        and f'FROM "{team_table}"' in sql
        and f'"{team_table}".SPACE_ID' in sql
        and f'"{team_table}".DELETED_AT IS NULL' in sql
    )
    member_update = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith(f'UPDATE "{member_table}"')
    )
    team_update = next(
        i
        for i, sql in enumerate(statements)
        if sql.startswith(f'UPDATE "{team_table}"')
    )
    assert team_lock_select < member_update < team_update


def test_two_sqlite_sessions_keep_both_concurrent_capacity_changes(db_sessionmaker):
    """SQLite proxy coverage for two sessions; Oracle lock behavior is compiled above."""
    team_id = _seed_team(db_sessionmaker)
    engine = db_sessionmaker.kw["bind"]
    if engine.dialect.name != "sqlite":
        pytest.skip("Two-session behavior here is a SQLite proxy, not a live Oracle test")

    ready = Barrier(2)

    def add_member(name: str, hours: int) -> None:
        with db_sessionmaker() as session:
            ready.wait(timeout=10)
            team = teams_route._lock_active_team(session, team_id, _SPACE)
            member = TeamMember(
                space_id=_SPACE.space_id,
                team_id=team_id,
                member_name=name,
                role="member",
                capacity_unit="fte_month",
                hours_capacity=hours,
                capacity_fte_month=hours / 40,
            )
            session.add(member)
            teams_route._commit_team_member_capacity_change(
                session, team, _SPACE, member_to_refresh=member
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(add_member, "First concurrent member", 25),
            executor.submit(add_member, "Second concurrent member", 40),
        ]
        for future in futures:
            future.result(timeout=20)

    with db_sessionmaker() as session:
        team = session.query(Team).filter(Team.team_id == team_id).one()
        members = (
            session.query(TeamMember)
            .filter(TeamMember.team_id == team_id)
            .filter(TeamMember.deleted_at.is_(None))
            .all()
        )

    assert len(members) == 2
    assert team.default_capacity_per_week == 65
    assert team.default_capacity_fte_month == pytest.approx(1.625)
