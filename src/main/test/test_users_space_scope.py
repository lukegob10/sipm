import pytest
from types import SimpleNamespace

from backend.app import deps as deps_module
from backend.app.models import Space, SpaceMembership, User
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


def _seed_users_in_two_spaces(db_sessionmaker):
    with db_sessionmaker() as session:
        space_a = Space(space_id="space-users-a", name="Users A", slug="users-a", is_active=True)
        space_b = Space(space_id="space-users-b", name="Users B", slug="users-b", is_active=True)
        session.add_all([space_a, space_b])

        user_a = User(
            user_id="user-a",
            soeid="usera",
            email="usera@example.com",
            display_name="User A",
            password_hash="x",
            role="user",
            is_active=True,
        )
        user_b = User(
            user_id="user-b",
            soeid="userb",
            email="userb@example.com",
            display_name="User B",
            password_hash="x",
            role="user",
            is_active=True,
        )
        session.add_all([user_a, user_b])

        membership_a = SpaceMembership(
            membership_id="membership-a",
            space_id=space_a.space_id,
            user_id=user_a.user_id,
            role="member",
            status="active",
        )
        membership_b = SpaceMembership(
            membership_id="membership-b",
            space_id=space_b.space_id,
            user_id=user_b.user_id,
            role="member",
            status="active",
        )
        session.add_all([membership_a, membership_b])
        session.commit()
        return space_a.space_id, space_b.space_id


def _set_current_space_override(space_id: str, role: str = "member"):
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
        space_id=space_id,
        space_name="Users Space",
        is_global_admin=False,
        space_role=role,
    )


def _restore_current_space_override(original):
    if original is None:
        fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
    else:
        fastapi_app.dependency_overrides[deps_module.current_space] = original


@pytest.mark.anyio
async def test_list_users_is_scoped_to_active_space(client, db_sessionmaker):
    space_a, _ = _seed_users_in_two_spaces(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_a, role="member")
        resp = await client.get("/project-manager/api/users")
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert len(rows) == 1
        assert rows[0]["soeid"] == "usera"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_update_user_requires_space_admin_and_space_membership(client, db_sessionmaker):
    space_a, _ = _seed_users_in_two_spaces(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_a, role="member")
        denied = await client.patch(
            "/project-manager/api/users/by-soeid/usera",
            json={"team_tag": "Platform"},
        )
        assert denied.status_code == 403, denied.text

        _set_current_space_override(space_a, role="space_admin")
        not_in_space = await client.patch(
            "/project-manager/api/users/by-soeid/userb",
            json={"team_tag": "Platform"},
        )
        assert not_in_space.status_code == 404, not_in_space.text
        assert not_in_space.json()["detail"] == "User not found in active space"

        updated = await client.patch(
            "/project-manager/api/users/by-soeid/usera",
            json={"team_tag": "Platform", "capacity_fte_month": 0.9},
        )
        assert updated.status_code == 200, updated.text
        payload = updated.json()
        assert payload["team_tag"] == "Platform"
        assert payload["capacity_fte_month"] == pytest.approx(0.9)
        assert payload["capacity_hours"] == 36
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_import_users_links_new_users_to_active_space(client, db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(space_id="space-users-import", name="Users Import", slug="users-import", is_active=True)
        session.add(space)
        session.commit()
        space_id = space.space_id

    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")
        csv_text = "\n".join(
            [
                "soeid,display_name,team_tag,capacity_fte_month",
                "newuser,New User,Team A,0.80",
            ]
        )
        resp = await client.post(
            "/project-manager/api/users/import",
            content=csv_text.encode("utf-8"),
            headers={"Content-Type": "text/csv"},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["created"] == 1
        assert body["updated"] == 0

        with db_sessionmaker() as session:
            user = session.query(User).filter(User.soeid == "newuser").first()
            assert user is not None
            membership = (
                session.query(SpaceMembership)
                .filter(SpaceMembership.space_id == space_id)
                .filter(SpaceMembership.user_id == user.user_id)
                .filter(SpaceMembership.deleted_at.is_(None))
                .first()
            )
            assert membership is not None
            assert membership.status == "active"
            assert membership.role == "member"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_non_global_admin_cannot_modify_global_admin_account(client, db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(space_id="space-global-admin-lock", name="Global Admin Lock", slug="global-admin-lock", is_active=True)
        target = User(
            user_id="target-global-admin",
            soeid="globaladmin1",
            email="globaladmin1@example.com",
            display_name="Global Admin 1",
            password_hash="x",
            role="global_admin",
            is_active=True,
        )
        membership = SpaceMembership(
            membership_id="membership-global-admin-1",
            space_id=space.space_id,
            user_id=target.user_id,
            role="space_admin",
            status="active",
        )
        session.add_all([space, target, membership])
        session.commit()

    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    original_require_user = fastapi_app.dependency_overrides.get(deps_module.require_user)
    original_current_user = fastapi_app.dependency_overrides.get(deps_module.current_user)
    try:
        _set_current_space_override("space-global-admin-lock", role="space_admin")
        actor = SimpleNamespace(user_id="space-admin-actor", role="user", is_active=True, display_name="Actor", soeid="actor1")
        fastapi_app.dependency_overrides[deps_module.require_user] = lambda: actor
        fastapi_app.dependency_overrides[deps_module.current_user] = lambda: actor

        resp = await client.patch(
            "/project-manager/api/users/by-soeid/globaladmin1",
            json={"team_tag": "Platform"},
        )
        assert resp.status_code == 403, resp.text
        assert resp.json()["detail"] == "Only global admin can modify global admin accounts"
    finally:
        _restore_current_space_override(original_current_space)
        if original_require_user is None:
            fastapi_app.dependency_overrides.pop(deps_module.require_user, None)
        else:
            fastapi_app.dependency_overrides[deps_module.require_user] = original_require_user
        if original_current_user is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_user, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_user] = original_current_user


@pytest.mark.anyio
async def test_global_admin_can_issue_password_reset_by_soeid(client, db_sessionmaker):
    with db_sessionmaker() as session:
        target = User(
            user_id="password-reset-target",
            soeid="resetuser1",
            email="resetuser1@example.com",
            display_name="Reset User",
            password_hash="x",
            role="user",
            is_active=True,
        )
        session.add(target)
        session.commit()

    resp = await client.post(
        "/project-manager/api/users/by-soeid/resetuser1/password-reset-request",
        json={"expires_minutes": 45},
    )
    assert resp.status_code == 201, resp.text
    payload = resp.json()
    assert payload["status"] == "issued"
    assert payload["temp_password"]
    assert payload["expires_at"]

    with db_sessionmaker() as session:
        user = session.query(User).filter(User.soeid == "resetuser1").first()
        assert user is not None
        assert user.force_password_reset is True
        assert user.temp_password_hash
        assert user.temp_password_expires_at is not None


@pytest.mark.anyio
async def test_cannot_deactivate_last_global_admin(client, db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(space_id="space-last-global-admin", name="Last Global Admin", slug="last-global-admin", is_active=True)
        first_admin = User(
            user_id="global-admin-a",
            soeid="globaladmina",
            email="globaladmina@example.com",
            display_name="Global Admin A",
            password_hash="x",
            role="global_admin",
            is_active=True,
        )
        first_membership = SpaceMembership(
            membership_id="membership-global-admin-a",
            space_id=space.space_id,
            user_id=first_admin.user_id,
            role="space_admin",
            status="active",
        )
        session.add_all([space, first_admin, first_membership])
        session.commit()

    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override("space-last-global-admin", role="space_admin")
        blocked = await client.patch(
            "/project-manager/api/users/by-soeid/globaladmina",
            json={"is_active": False},
        )
        assert blocked.status_code == 400, blocked.text
        assert blocked.json()["detail"] == "At least one active global_admin is required"

        with db_sessionmaker() as session:
            second_admin = User(
                user_id="global-admin-b",
                soeid="globaladminb",
                email="globaladminb@example.com",
                display_name="Global Admin B",
                password_hash="x",
                role="global_admin",
                is_active=True,
            )
            second_membership = SpaceMembership(
                membership_id="membership-global-admin-b",
                space_id="space-last-global-admin",
                user_id=second_admin.user_id,
                role="space_admin",
                status="active",
            )
            session.add_all([second_admin, second_membership])
            session.commit()

        allowed = await client.patch(
            "/project-manager/api/users/by-soeid/globaladmina",
            json={"is_active": False},
        )
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["is_active"] is False
    finally:
        _restore_current_space_override(original_current_space)
