from types import SimpleNamespace

import pytest

from backend.app import deps as deps_module
from backend.app.models import User
from backend.main import app as fastapi_app


def _seed_global_admin_users(db_sessionmaker):
    with db_sessionmaker() as session:
        first = User(
            user_id="global-admin-1",
            soeid="ga1",
            email="ga1@example.com",
            display_name="Global Admin One",
            password_hash="x",
            role="global_admin",
            is_active=True,
        )
        second = User(
            user_id="regular-user-1",
            soeid="user1",
            email="user1@example.com",
            display_name="Regular User One",
            password_hash="x",
            role="user",
            is_active=True,
        )
        session.add_all([first, second])
        session.commit()


@pytest.mark.anyio
async def test_global_admin_role_endpoints_by_user_id_and_soeid(client, db_sessionmaker):
    _seed_global_admin_users(db_sessionmaker)

    list_before = await client.get("/project-manager/api/users/global-admins")
    assert list_before.status_code == 200, list_before.text
    assert [u["soeid"] for u in list_before.json()] == ["ga1"]

    grant_by_id = await client.post("/project-manager/api/users/regular-user-1/global-admin")
    assert grant_by_id.status_code == 200, grant_by_id.text
    assert grant_by_id.json()["role"] == "global_admin"

    grant_by_soeid = await client.post("/project-manager/api/users/by-soeid/user1/global-admin")
    assert grant_by_soeid.status_code == 200, grant_by_soeid.text
    assert grant_by_soeid.json()["role"] == "global_admin"

    revoke_by_soeid = await client.delete("/project-manager/api/users/by-soeid/user1/global-admin")
    assert revoke_by_soeid.status_code == 200, revoke_by_soeid.text
    assert revoke_by_soeid.json()["role"] == "user"

    with db_sessionmaker() as session:
        updated = session.query(User).filter(User.user_id == "regular-user-1").first()
        assert updated is not None
        assert updated.role == "user"


@pytest.mark.anyio
async def test_cannot_revoke_last_active_global_admin_via_global_admin_endpoint(client, db_sessionmaker):
    with db_sessionmaker() as session:
        admin = User(
            user_id="only-global-admin",
            soeid="onlyadmin",
            email="onlyadmin@example.com",
            display_name="Only Admin",
            password_hash="x",
            role="global_admin",
            is_active=True,
        )
        session.add(admin)
        session.commit()

    blocked = await client.delete("/project-manager/api/users/only-global-admin/global-admin")
    assert blocked.status_code == 400, blocked.text
    assert blocked.json()["detail"] == "At least one active global_admin is required"


@pytest.mark.anyio
async def test_non_global_admin_cannot_manage_global_admin_role(client, db_sessionmaker):
    _seed_global_admin_users(db_sessionmaker)
    original_require_user = fastapi_app.dependency_overrides.get(deps_module.require_user)
    original_current_user = fastapi_app.dependency_overrides.get(deps_module.current_user)
    try:
        actor = SimpleNamespace(user_id="space-admin-actor", role="user", is_active=True, display_name="Actor", soeid="actor1")
        fastapi_app.dependency_overrides[deps_module.require_user] = lambda: actor
        fastapi_app.dependency_overrides[deps_module.current_user] = lambda: actor

        list_resp = await client.get("/project-manager/api/users/global-admins")
        assert list_resp.status_code == 403, list_resp.text
        assert list_resp.json()["detail"] == "Global admin required"

        grant_resp = await client.post("/project-manager/api/users/regular-user-1/global-admin")
        assert grant_resp.status_code == 403, grant_resp.text
        assert grant_resp.json()["detail"] == "Global admin required"
    finally:
        if original_require_user is None:
            fastapi_app.dependency_overrides.pop(deps_module.require_user, None)
        else:
            fastapi_app.dependency_overrides[deps_module.require_user] = original_require_user
        if original_current_user is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_user, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_user] = original_current_user


@pytest.mark.anyio
async def test_global_admin_routes_accept_legacy_formatted_role_values(client, db_sessionmaker):
    with db_sessionmaker() as session:
        legacy = User(
            user_id="legacy-global-admin",
            soeid="legacyga",
            email="legacyga@example.com",
            display_name="Legacy Global Admin",
            password_hash="x",
            role="Global Admin",
            is_active=True,
        )
        session.add(legacy)
        session.commit()

    original_require_user = fastapi_app.dependency_overrides.get(deps_module.require_user)
    original_current_user = fastapi_app.dependency_overrides.get(deps_module.current_user)
    try:
        actor = SimpleNamespace(
            user_id="legacy-admin-actor",
            role="global-admin",
            is_active=True,
            display_name="Legacy Actor",
            soeid="legacyactor",
        )
        fastapi_app.dependency_overrides[deps_module.require_user] = lambda: actor
        fastapi_app.dependency_overrides[deps_module.current_user] = lambda: actor

        list_resp = await client.get("/project-manager/api/users/global-admins")
        assert list_resp.status_code == 200, list_resp.text
        assert [u["soeid"] for u in list_resp.json()] == ["legacyga"]
    finally:
        if original_require_user is None:
            fastapi_app.dependency_overrides.pop(deps_module.require_user, None)
        else:
            fastapi_app.dependency_overrides[deps_module.require_user] = original_require_user
        if original_current_user is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_user, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_user] = original_current_user
