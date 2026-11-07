from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Space, SpaceMembership, User


@pytest.mark.anyio
async def test_space_member_list_uses_bounded_user_lookup(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(Space(space_id="large-space", name="Large Space", slug="large-space"))
        for index in range(1001):
            user_id = f"user-{index:04}"
            session.add(User(
                user_id=user_id, soeid=user_id, email=f"{user_id}@example.com", display_name=f"User {index:04}",
                password_hash="unused", role="user", is_active=True,
            ))
            session.add(SpaceMembership(
                membership_id=f"member-{index:04}", space_id="large-space", user_id=user_id,
                role="member", status="active",
            ))
        session.commit()

    sizes = []
    engine = db_sessionmaker.kw["bind"]

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT") and "TB_TA_PM_USERS" in statement:
            sizes.append(len(parameters))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = await client.get("/project-manager/api/spaces/large-space/members")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    assert len(response.json()) == 1001
    assert {row["user_display_name"] for row in response.json()} == {f"User {index:04}" for index in range(1001)}
    assert sizes and max(sizes) <= 500, sizes


@pytest.mark.anyio
async def test_requestable_spaces_avoids_unbounded_membership_id_list(client, db_sessionmaker):
    with db_sessionmaker() as session:
        for index in range(1001):
            space_id = f"space-{index:04}"
            session.add(Space(space_id=space_id, name=f"Space {index:04}", slug=space_id))
            session.add(SpaceMembership(
                space_id=space_id, user_id="test-user", role="member", status="active",
            ))
        session.add_all([
            Space(space_id="available-space", name="Available", slug="available"),
            Space(space_id="inactive-space", name="Inactive Membership", slug="inactive"),
            Space(space_id="deleted-space", name="Deleted Membership", slug="deleted"),
        ])
        session.add_all([
            SpaceMembership(space_id="inactive-space", user_id="test-user", role="member", status="inactive"),
            SpaceMembership(
                space_id="deleted-space", user_id="test-user", role="member", status="active",
                deleted_at=datetime.now(timezone.utc),
            ),
        ])
        session.commit()

    sizes = []
    engine = db_sessionmaker.kw["bind"]

    def capture(_conn, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            sizes.append(len(parameters))

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = await client.get("/project-manager/api/spaces/requestable")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200, response.text
    assert [row["space_id"] for row in response.json()] == ["available-space", "deleted-space", "inactive-space"]
    assert sizes and max(sizes) <= 500, sizes
