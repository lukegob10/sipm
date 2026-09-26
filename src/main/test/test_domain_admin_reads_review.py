from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Space, SpaceAccessRequest, Team, TeamMember, User


@pytest.mark.anyio
@pytest.mark.parametrize("team_count", [0, 1, 12])
async def test_team_list_batches_members_and_preserves_scope(client, db_sessionmaker, team_count):
    now = datetime.now(timezone.utc)
    with db_sessionmaker() as session:
        for index in range(team_count):
            session.add(Team(
                team_id=f"team-{index}", space_id="test-space", name=f"Team {index}",
                created_at=now + timedelta(seconds=index),
            ))
            session.add(TeamMember(
                team_id=f"team-{index}", space_id="test-space", member_name=f"Member {index}",
            ))
        session.add_all([
            Team(team_id="foreign", space_id="other-space", name="Foreign"),
            Team(team_id="deleted", space_id="test-space", name="Deleted", deleted_at=now),
            TeamMember(team_id="foreign", space_id="other-space", member_name="Foreign member"),
            TeamMember(team_id="deleted", space_id="test-space", member_name="Deleted team's member"),
        ])
        if team_count:
            session.add_all([
                TeamMember(team_id="team-0", space_id="test-space", member_name="Deleted member", deleted_at=now),
                TeamMember(team_id="team-0", space_id="other-space", member_name="Mismatched member"),
            ])
        session.commit()

    statements = []
    engine = db_sessionmaker.kw["bind"]

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = await client.get("/project-manager/api/teams")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["team_id"] for row in rows] == [f"team-{index}" for index in range(team_count)]
    assert [row["members"][0]["member_name"] for row in rows] == [
        f"Member {index}" for index in range(team_count)
    ]
    assert all(len(row["members"]) == 1 for row in rows)
    assert len(statements) <= 2, f"Team list issued {len(statements)} SELECTs"


@pytest.mark.anyio
@pytest.mark.parametrize("request_count", [0, 1, 12, 501])
async def test_access_request_list_batches_related_labels(client, db_sessionmaker, request_count):
    now = datetime.now(timezone.utc)
    with db_sessionmaker() as session:
        session.add(User(
            user_id="test-user", soeid="tu12345", email="test@example.com",
            display_name="Test User", password_hash="unused",
        ))
        for index in range(request_count):
            session.add(Space(space_id=f"space-{index}", name=f"Space {index}", slug=f"space-{index}"))
            session.add(SpaceAccessRequest(
                request_id=f"request-{index}", space_id=f"space-{index}", requester_user_id="test-user",
                requested_role="member", status="pending", created_at=now + timedelta(seconds=index),
            ))
        session.commit()

    statements = []
    engine = db_sessionmaker.kw["bind"]

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = await client.get("/project-manager/api/spaces/access-requests")
    finally:
        event.remove(engine, "before_cursor_execute", capture)

    assert response.status_code == 200, response.text
    rows = response.json()
    assert [row["space_name"] for row in rows] == [f"Space {index}" for index in reversed(range(request_count))]
    assert all(row["requester_soeid"] == "tu12345" for row in rows)
    assert all(row["requester_display_name"] == "Test User" for row in rows)
    query_limit = 1 + 2 * ((request_count + 499) // 500)
    assert len(statements) <= query_limit, f"Access request list issued {len(statements)} SELECTs"
