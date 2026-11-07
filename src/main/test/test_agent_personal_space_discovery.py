from __future__ import annotations

import httpx
import pytest

from backend.app import deps
from backend.app.models import ApiToken, Space, SpaceMembership, User
from backend.app.services.api_tokens import hash_api_token
from backend.main import app


@pytest.mark.anyio
async def test_agent_space_discovery_respects_nonowner_personal_boundary(db_sessionmaker):
    tokens = {name: f"sipm_pat_{name}_test" for name in ("owner", "other", "admin")}
    with db_sessionmaker() as session:
        for name in tokens:
            session.add(User(
                user_id=name, soeid=name, email=f"{name}@example.com", display_name=name,
                password_hash="unused", role="global_admin" if name == "admin" else "user", is_active=True,
            ))
            session.add(ApiToken(
                user_id=name, name="test", token_hash=hash_api_token(tokens[name]), created_by_user_id="admin",
            ))
        session.add_all([
            Space(space_id="private", name="Private", slug="private", space_kind="personal", owner_user_id="owner"),
            Space(space_id="work", name="Work", slug="work", space_kind="collaboration"),
            SpaceMembership(space_id="private", user_id="owner", role="space_admin", status="active"),
            SpaceMembership(space_id="private", user_id="other", role="member", status="active"),
            SpaceMembership(space_id="work", user_id="other", role="member", status="active"),
        ])
        session.commit()

    def test_db():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[deps.get_db] = test_db
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            async def get(path, actor):
                return await client.get(path, headers={"Authorization": f"Bearer {tokens[actor]}"})

            other_list = await get("/project-manager/api/agent/spaces", "other")
            assert other_list.status_code == 200
            assert [space["space_id"] for space in other_list.json()["records"]] == ["work"]
            assert (await get("/project-manager/api/agent/spaces/private", "other")).status_code == 404

            owner_list = await get("/project-manager/api/agent/spaces", "owner")
            assert [space["space_id"] for space in owner_list.json()["records"]] == ["private"]
            assert (await get("/project-manager/api/agent/spaces/private", "owner")).status_code == 200

            admin_list = await get("/project-manager/api/agent/spaces", "admin")
            assert {space["space_id"] for space in admin_list.json()["records"]} == {"private", "work"}
            assert (await get("/project-manager/api/agent/spaces/private", "admin")).status_code == 200
    finally:
        app.dependency_overrides.clear()
