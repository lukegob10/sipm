import pytest
from fastapi import HTTPException

from backend.app import deps as deps_module
from backend.app.models import Space, SpaceMembership, User
from backend.app.services.smart_cache import clear_cache
from backend.app.services.spaces import SpaceContext, resolve_active_space_context
from backend.main import app as fastapi_app


def _seed_space_with_members(db_sessionmaker, *, admin_count: int, include_member: bool = False):
    with db_sessionmaker() as session:
        space = Space(
            space_id="space-admin-guard",
            name="Admin Guard Space",
            slug="admin-guard-space",
            is_active=True,
        )
        session.add(space)

        admin_membership_ids = []
        for idx in range(admin_count):
            user = User(
                user_id=f"admin-user-{idx}",
                soeid=f"admin{idx}",
                email=f"admin{idx}@example.com",
                display_name=f"Admin {idx}",
                password_hash="x",
                role="user",
                is_active=True,
            )
            session.add(user)
            membership = SpaceMembership(
                membership_id=f"admin-membership-{idx}",
                space_id=space.space_id,
                user_id=user.user_id,
                role="space_admin",
                status="active",
            )
            session.add(membership)
            admin_membership_ids.append(membership.membership_id)

        member_membership_id = None
        if include_member:
            member = User(
                user_id="member-user-0",
                soeid="member0",
                email="member0@example.com",
                display_name="Member 0",
                password_hash="x",
                role="user",
                is_active=True,
            )
            session.add(member)
            member_membership = SpaceMembership(
                membership_id="member-membership-0",
                space_id=space.space_id,
                user_id=member.user_id,
                role="member",
                status="active",
            )
            session.add(member_membership)
            member_membership_id = member_membership.membership_id

        session.commit()
        return space.space_id, admin_membership_ids, member_membership_id


def _set_current_space_override(space_id: str, role: str = "space_admin"):
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
        space_id=space_id,
        space_name="Admin Guard Space",
        is_global_admin=False,
        space_role=role,
    )


def _restore_current_space_override(original):
    if original is None:
        fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
    else:
        fastapi_app.dependency_overrides[deps_module.current_space] = original


def test_resolve_active_space_does_not_create_default_membership_for_unassigned_user(db_sessionmaker):
    with db_sessionmaker() as session:
        user = User(
            user_id="space-unassigned-user",
            soeid="nomember",
            email="nomember@example.com",
            display_name="No Member",
            password_hash="x",
            role="user",
            is_active=True,
        )
        session.add(user)
        session.commit()

        with pytest.raises(HTTPException) as exc:
            resolve_active_space_context(session, user, requested_space_id=None)

        assert exc.value.status_code == 403
        assert exc.value.headers["X-Error-Code"] == "NO_ACTIVE_SPACE"
        assert session.query(SpaceMembership).filter(SpaceMembership.user_id == user.user_id).count() == 0


@pytest.mark.anyio
async def test_cannot_remove_last_active_space_admin(client, db_sessionmaker):
    space_id, admin_memberships, _ = _seed_space_with_members(db_sessionmaker, admin_count=1)
    membership_id = admin_memberships[0]
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")
        demote = await client.patch(
            f"/project-manager/api/spaces/{space_id}/members/{membership_id}",
            json={"role": "member"},
        )
        assert demote.status_code == 400, demote.text
        assert demote.json()["detail"] == "Space must retain at least one active space_admin"

        deactivate = await client.patch(
            f"/project-manager/api/spaces/{space_id}/members/{membership_id}",
            json={"status": "inactive"},
        )
        assert deactivate.status_code == 400, deactivate.text
        assert deactivate.json()["detail"] == "Space must retain at least one active space_admin"

        delete_resp = await client.delete(f"/project-manager/api/spaces/{space_id}/members/{membership_id}")
        assert delete_resp.status_code == 400, delete_resp.text
        assert delete_resp.json()["detail"] == "Space must retain at least one active space_admin"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_create_space_rejects_duplicate_name_with_clean_client_error(client):
    first = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Delivery Space", "slug": "delivery-space"},
    )
    assert first.status_code == 201, first.text

    duplicate = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Delivery Space", "slug": "delivery-space-2"},
    )
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["detail"] == "Space name already exists"


@pytest.mark.anyio
async def test_update_space_rejects_duplicate_name_with_clean_client_error(client):
    first = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Delivery Space", "slug": "delivery-space"},
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Planning Space", "slug": "planning-space"},
    )
    assert second.status_code == 201, second.text

    second_space_id = second.json()["space_id"]
    duplicate = await client.patch(
        f"/project-manager/api/spaces/{second_space_id}",
        json={"name": "Delivery Space"},
    )
    assert duplicate.status_code == 400, duplicate.text
    assert duplicate.json()["detail"] == "Space name already exists"


@pytest.mark.anyio
async def test_can_change_admin_membership_when_another_admin_exists(client, db_sessionmaker):
    space_id, admin_memberships, member_membership_id = _seed_space_with_members(
        db_sessionmaker,
        admin_count=2,
        include_member=True,
    )
    first_admin = admin_memberships[0]
    second_admin = admin_memberships[1]
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")
        demote = await client.patch(
            f"/project-manager/api/spaces/{space_id}/members/{first_admin}",
            json={"role": "member"},
        )
        assert demote.status_code == 200, demote.text
        assert demote.json()["role"] == "member"

        delete_member = await client.delete(f"/project-manager/api/spaces/{space_id}/members/{member_membership_id}")
        assert delete_member.status_code == 204, delete_member.text

        delete_last_admin = await client.delete(f"/project-manager/api/spaces/{space_id}/members/{second_admin}")
        assert delete_last_admin.status_code == 400, delete_last_admin.text
        assert delete_last_admin.json()["detail"] == "Space must retain at least one active space_admin"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_inactive_admin_user_does_not_count_as_remaining_active_space_admin(client, db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(
            space_id="space-inactive-admin-guard",
            name="Inactive Admin Guard Space",
            slug="inactive-admin-guard-space",
            is_active=True,
        )
        active_admin = User(
            user_id="active-admin-guard-user",
            soeid="activeguard",
            email="activeguard@example.com",
            display_name="Active Guard",
            password_hash="x",
            role="user",
            is_active=True,
        )
        inactive_admin = User(
            user_id="inactive-admin-guard-user",
            soeid="inactiveguard",
            email="inactiveguard@example.com",
            display_name="Inactive Guard",
            password_hash="x",
            role="user",
            is_active=False,
        )
        active_membership = SpaceMembership(
            membership_id="active-admin-guard-membership",
            space_id=space.space_id,
            user_id=active_admin.user_id,
            role="space_admin",
            status="active",
        )
        inactive_membership = SpaceMembership(
            membership_id="inactive-admin-guard-membership",
            space_id=space.space_id,
            user_id=inactive_admin.user_id,
            role="space_admin",
            status="active",
        )
        session.add_all([space, active_admin, inactive_admin, active_membership, inactive_membership])
        session.commit()

    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override("space-inactive-admin-guard", role="space_admin")
        demote = await client.patch(
            "/project-manager/api/spaces/space-inactive-admin-guard/members/active-admin-guard-membership",
            json={"role": "member"},
        )
        assert demote.status_code == 400, demote.text
        assert demote.json()["detail"] == "Space must retain at least one active space_admin"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_add_member_by_soeid_and_restore_soft_deleted_membership(client, db_sessionmaker):
    space_id, _, member_membership_id = _seed_space_with_members(
        db_sessionmaker,
        admin_count=1,
        include_member=True,
    )
    with db_sessionmaker() as session:
        new_user = User(
            user_id="member-user-new",
            soeid="membernew",
            email="membernew@example.com",
            display_name="Member New",
            password_hash="x",
            role="user",
            is_active=True,
        )
        session.add(new_user)
        session.commit()
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")

        created = await client.post(
            f"/project-manager/api/spaces/{space_id}/members/by-soeid",
            json={"soeid": "membernew", "role": "member", "status": "active"},
        )
        assert created.status_code == 201, created.text
        assert created.json()["role"] == "member"
        assert created.json()["status"] == "active"

        delete_resp = await client.delete(f"/project-manager/api/spaces/{space_id}/members/{member_membership_id}")
        assert delete_resp.status_code == 204, delete_resp.text

        restored = await client.post(
            f"/project-manager/api/spaces/{space_id}/members/by-soeid",
            json={"soeid": "member0", "role": "space_admin", "status": "active"},
        )
        assert restored.status_code == 201, restored.text
        assert restored.json()["membership_id"] == member_membership_id
        assert restored.json()["role"] == "space_admin"

        duplicate = await client.post(
            f"/project-manager/api/spaces/{space_id}/members/by-soeid",
            json={"soeid": "member0"},
        )
        assert duplicate.status_code == 400, duplicate.text
        assert duplicate.json()["detail"] == "Membership already exists"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_list_space_members_includes_user_identity_fields(client, db_sessionmaker):
    space_id, _, member_membership_id = _seed_space_with_members(
        db_sessionmaker,
        admin_count=1,
        include_member=True,
    )
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")
        resp = await client.get(f"/project-manager/api/spaces/{space_id}/members")
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        target = next((row for row in rows if row["membership_id"] == member_membership_id), None)
        assert target is not None
        assert target["user_soeid"] == "member0"
        assert target["user_display_name"] == "Member 0"
        assert target["user_email"] == "member0@example.com"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_space_membership_changes_invalidate_cached_user_roster(client, db_sessionmaker):
    clear_cache()
    space_id, _admin_memberships, _member_membership_id = _seed_space_with_members(
        db_sessionmaker,
        admin_count=1,
        include_member=False,
    )
    with db_sessionmaker() as session:
        new_user = User(
            user_id="cache-member-user",
            soeid="cachemember",
            email="cachemember@example.com",
            display_name="Cache Member",
            password_hash="x",
            role="user",
            is_active=True,
        )
        session.add(new_user)
        session.commit()

    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")

        initial = await client.get("/project-manager/api/users")
        assert initial.status_code == 200, initial.text
        assert {row["soeid"] for row in initial.json()} == {"admin0"}

        added = await client.post(
            f"/project-manager/api/spaces/{space_id}/members/by-soeid",
            json={"soeid": "cachemember", "role": "member", "status": "active"},
        )
        assert added.status_code == 201, added.text

        refreshed = await client.get("/project-manager/api/users")
        assert refreshed.status_code == 200, refreshed.text
        assert {row["soeid"] for row in refreshed.json()} == {"admin0", "cachemember"}
    finally:
        clear_cache()
        _restore_current_space_override(original_current_space)
