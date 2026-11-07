from __future__ import annotations

import pytest

from test_agent_api import _auth_headers, _seed_agent_token, agent_client, override_db_only  # noqa: F401
from backend.app.models import SpaceMembership, Team, TeamMember, User
from backend.app.services.agent_pagination import encode_position_cursor


@pytest.mark.anyio
async def test_blank_names_have_usable_signed_cursors_and_invalid_positions_are_rejected(agent_client, db_sessionmaker):  # noqa: F811
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("Empty strings are represented as NULL by Oracle")
    token, space_id = _seed_agent_token(db_sessionmaker)
    with db_sessionmaker() as session:
        session.add(User(user_id="blank-person", soeid="blankperson", email="blank@example.com",
                         display_name="", password_hash="unused", role="user", is_active=True))
        session.add(SpaceMembership(space_id=space_id, user_id="blank-person", role="member", status="active"))
        session.add_all([
            Team(team_id="blank-team", space_id=space_id, name=""),
            Team(team_id="named-team", space_id=space_id, name="Named"),
            TeamMember(team_member_id="blank-member", team_id="blank-team", space_id=space_id, member_name=""),
            TeamMember(team_member_id="named-member", team_id="blank-team", space_id=space_id, member_name="Named"),
        ])
        session.commit()

    cases = [
        ("/people", "agent_people_v1", {"space_id": space_id, "q": None, "soeid": None, "role": None}, "user_id"),
        ("/teams", "agent_teams_v1", {"space_id": space_id, "q": None}, "team_id"),
        ("/teams/blank-team/members", "agent_team_members_v1", {"space_id": space_id, "team_id": "blank-team"}, "team_member_id"),
    ]
    headers = _auth_headers(token, space_id)
    for path, scope, filters, id_field in cases:
        first = await agent_client.get(f"/project-manager/api/agent{path}", headers=headers, params={"limit": 1})
        assert first.status_code == 200, first.text
        assert first.json()["has_more"] is True and first.json()["next_cursor"]
        second = await agent_client.get(f"/project-manager/api/agent{path}", headers=headers,
                                        params={"limit": 1, "cursor": first.json()["next_cursor"]})
        assert second.status_code == 200, second.text
        assert second.json()["records"]
        for position in ({id_field: "id"}, {"name": 123, id_field: "id"}, {"name": "", id_field: ""}, {"name": ""}):
            cursor = encode_position_cursor(scope=scope, filters=filters, position=position)
            invalid = await agent_client.get(f"/project-manager/api/agent{path}", headers=headers,
                                             params={"limit": 1, "cursor": cursor})
            assert invalid.status_code == 400, invalid.text
            assert invalid.json()["code"] == "INVALID_CURSOR"


@pytest.mark.anyio
async def test_people_role_filter_matches_legacy_admin_role_spellings(agent_client, db_sessionmaker):  # noqa: F811
    token, space_id = _seed_agent_token(db_sessionmaker)
    with db_sessionmaker() as session:
        for index, role in enumerate(("space-admin", " SPACE ADMIN ", "space_admin")):
            user_id = f"admin-{index}"
            session.add(User(user_id=user_id, soeid=user_id, email=f"{user_id}@example.com",
                             display_name=f"Admin {index}", password_hash="unused", role="user", is_active=True))
            session.add(SpaceMembership(space_id=space_id, user_id=user_id, role=role, status="active"))
        session.commit()

    headers = _auth_headers(token, space_id)
    expected = {"admin-0": "space-admin", "admin-1": " SPACE ADMIN ", "admin-2": "space_admin"}
    for role_filter in ("space_admin", "Space Admin", "space-admin"):
        response = await agent_client.get("/project-manager/api/agent/people", headers=headers, params={"role": role_filter})
        assert response.status_code == 200, response.text
        assert {row["user_id"]: row["membership_role"] for row in response.json()["records"]} == expected
    old_cursor = encode_position_cursor(
        scope="agent_people_v1", filters={"space_id": space_id, "q": None, "soeid": None, "role": "space-admin"},
        position={"name": "Admin 0", "user_id": "admin-0"},
    )
    second = await agent_client.get("/project-manager/api/agent/people", headers=headers,
                                    params={"role": "space-admin", "limit": 1, "cursor": old_cursor})
    assert second.status_code == 200, second.text
    assert second.json()["records"][0]["user_id"] == "admin-1"


@pytest.mark.anyio
async def test_blank_space_name_has_usable_cursor_and_invalid_positions_are_rejected(agent_client, db_sessionmaker):  # noqa: F811
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("Empty strings are represented as NULL by Oracle")
    from backend.app.models import ApiToken, Space
    from backend.app.services.api_tokens import hash_api_token

    token, _ = _seed_agent_token(db_sessionmaker)
    with db_sessionmaker() as session:
        user_id = session.query(ApiToken.user_id).filter(ApiToken.token_hash == hash_api_token(token)).scalar()
        session.add(Space(space_id="blank-space", name="", slug="blank-space"))
        session.add(SpaceMembership(space_id="blank-space", user_id=user_id, role="member", status="active"))
        session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    path = "/project-manager/api/agent/spaces"
    first = await agent_client.get(path, headers=headers, params={"limit": 1})
    assert first.status_code == 200, first.text
    assert first.json()["records"][0]["space_id"] == "blank-space"
    assert first.json()["has_more"] and first.json()["next_cursor"]
    second = await agent_client.get(path, headers=headers, params={"limit": 1, "cursor": first.json()["next_cursor"]})
    assert second.status_code == 200, second.text
    assert second.json()["records"]

    filters = {"user_id": user_id, "space_id": None, "slug": None, "name": None}
    for position in ({"space_id": "id"}, {"name": 123, "space_id": "id"}, {"name": "", "space_id": ""}, {"name": ""}, {"name": "x", "space_id": 42}):
        cursor = encode_position_cursor(scope="agent_spaces_v1", filters=filters, position=position)
        invalid = await agent_client.get(path, headers=headers, params={"limit": 1, "cursor": cursor})
        assert invalid.status_code == 400, invalid.text
        assert invalid.json()["code"] == "INVALID_CURSOR"
