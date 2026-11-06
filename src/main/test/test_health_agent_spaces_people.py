from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Space, Team, TeamMember
from backend.app.services.agent_pagination import encode_position_cursor
from backend.app.services.agent_people import TEAMS_CURSOR_SCOPE, list_agent_teams
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("empty_page", ["space", "search", "cursor"])
def test_empty_agent_team_pages_skip_member_count_query(db_sessionmaker, empty_page):
    ctx = SpaceContext("health-space", "Health", False, "member")
    with db_sessionmaker() as session:
        session.add(Space(space_id=ctx.space_id, name=ctx.space_name, slug=ctx.space_id))
        if empty_page != "space":
            session.add(Team(team_id="health-team", space_id=ctx.space_id, name="Alpha"))
        session.commit()

        kwargs = {}
        if empty_page == "search":
            kwargs["q"] = "No matching teams"
        elif empty_page == "cursor":
            kwargs["cursor"] = encode_position_cursor(
                scope=TEAMS_CURSOR_SCOPE,
                filters={"space_id": ctx.space_id, "q": None},
                position={"name": "Alpha", "team_id": "health-team"},
            )

        statements = []

        def record_query(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", record_query)
        try:
            result = list_agent_teams(session, ctx, **kwargs)
        finally:
            event.remove(engine, "before_cursor_execute", record_query)

    assert result.model_dump() == {
        "space_id": ctx.space_id,
        "records": [],
        "next_cursor": None,
        "has_more": False,
    }
    assert len(statements) == 1


def test_agent_team_counts_stay_scoped_and_batched_per_nonempty_page(db_sessionmaker):
    ctx = SpaceContext("health-space", "Health", False, "member")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id=ctx.space_id, name=ctx.space_name, slug=ctx.space_id),
            Space(space_id="other-space", name="Other", slug="other-space"),
            Team(team_id="alpha", space_id=ctx.space_id, name="Alpha"),
            Team(team_id="beta", space_id=ctx.space_id, name="Beta"),
            Team(team_id="other-team", space_id="other-space", name="Other team"),
        ])
        session.flush()
        session.add_all([
            TeamMember(team_id="alpha", space_id=ctx.space_id, member_name="First"),
            TeamMember(team_id="alpha", space_id=ctx.space_id, member_name="Second"),
            TeamMember(
                team_id="alpha", space_id=ctx.space_id, member_name="Deleted",
                deleted_at=datetime.now(timezone.utc),
            ),
            TeamMember(team_id="alpha", space_id="other-space", member_name="Wrong space"),
            TeamMember(team_id="other-team", space_id="other-space", member_name="Other"),
        ])
        session.commit()

        statements = []

        def record_query(_connection, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        engine = session.get_bind()
        event.listen(engine, "before_cursor_execute", record_query)
        try:
            first = list_agent_teams(session, ctx, limit=1)
            assert len(statements) == 2
            statements.clear()
            second = list_agent_teams(session, ctx, limit=1, cursor=first.next_cursor)
            assert len(statements) == 2
        finally:
            event.remove(engine, "before_cursor_execute", record_query)

    assert [(row.team_id, row.member_count) for row in first.records] == [("alpha", 2)]
    assert first.has_more is True
    assert first.next_cursor
    assert [(row.team_id, row.member_count) for row in second.records] == [("beta", 0)]
    assert second.has_more is False
    assert second.next_cursor is None
