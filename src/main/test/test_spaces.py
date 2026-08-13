from concurrent.futures import ThreadPoolExecutor
from threading import Event
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import oracle

from backend.app import deps as deps_module
from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import spaces as spaces_routes
from backend.app.routes import users as users_routes
from backend.app.schemas import SpaceMembershipUpdate, UserUpdate
from backend.app.services.smart_cache import clear_cache
from backend.app.services.spaces import SpaceContext, resolve_active_space_context
from backend.app.services import user_admin_guards
from backend.app.services.user_admin_guards import _space_admin_lock_statement
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
async def test_space_create_and_update_reject_blank_names(client):
    blank_create = await client.post(
        "/project-manager/api/spaces",
        json={"name": "   ", "slug": "blank-name-space"},
    )
    assert blank_create.status_code == 400, blank_create.text
    assert blank_create.json()["detail"] == "Space name is required"

    created = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Named Space", "slug": "named-space"},
    )
    assert created.status_code == 201, created.text
    space_id = created.json()["space_id"]

    blank_update = await client.patch(
        f"/project-manager/api/spaces/{space_id}",
        json={"name": "   "},
    )
    assert blank_update.status_code == 400, blank_update.text
    assert blank_update.json()["detail"] == "Space name is required"


@pytest.mark.anyio
async def test_space_admin_can_toggle_public_program_dashboard(client, db_sessionmaker):
    space_id, _, _ = _seed_space_with_members(db_sessionmaker, admin_count=1)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")
        enabled = await client.patch(
            f"/project-manager/api/spaces/{space_id}",
            json={"public_program_dashboard_enabled": True},
        )
        assert enabled.status_code == 200, enabled.text
        assert enabled.json()["public_program_dashboard_enabled"] is True

        disabled = await client.patch(
            f"/project-manager/api/spaces/{space_id}",
            json={"public_program_dashboard_enabled": False},
        )
        assert disabled.status_code == 200, disabled.text
        assert disabled.json()["public_program_dashboard_enabled"] is False
    finally:
        _restore_current_space_override(original_current_space)


def test_space_admin_guard_uses_ordered_oracle_row_lock():
    statement = _space_admin_lock_statement(["space-b", "space-a", "space-b"])

    sql = " ".join(
        str(statement.compile(dialect=oracle.dialect(), compile_kwargs={"literal_binds": True}))
        .replace('"', "")
        .split()
    ).lower()

    assert "space_id in ('space-a', 'space-b')" in sql
    assert sql.endswith("order by tb_ta_pm_spaces.space_id asc for update")


def test_membership_mutation_reloads_stale_row_after_space_lock(db_sessionmaker):
    space_id, admin_memberships, member_membership_id = _seed_space_with_members(
        db_sessionmaker,
        admin_count=1,
        include_member=True,
    )
    admin_membership_id = admin_memberships[0]
    ctx = SpaceContext(
        space_id=space_id,
        space_name="Admin Guard Space",
        is_global_admin=False,
        space_role="space_admin",
    )

    with db_sessionmaker() as stale_session:
        stale_member = (
            stale_session.query(SpaceMembership)
            .filter(SpaceMembership.membership_id == member_membership_id)
            .one()
        )
        assert stale_member.role == "member"

        with db_sessionmaker() as competing_session:
            spaces_routes.update_space_member(
                space_id,
                member_membership_id,
                SpaceMembershipUpdate(role="space_admin"),
                session=competing_session,
                ctx=ctx,
            )
            spaces_routes.update_space_member(
                space_id,
                admin_membership_id,
                SpaceMembershipUpdate(role="member"),
                session=competing_session,
                ctx=ctx,
            )

        with pytest.raises(HTTPException) as exc:
            spaces_routes.delete_space_member(
                space_id,
                member_membership_id,
                session=stale_session,
                ctx=ctx,
            )

        assert exc.value.status_code == 400
        assert exc.value.detail == "Space must retain at least one active space_admin"

    with db_sessionmaker() as verification_session:
        current_member = (
            verification_session.query(SpaceMembership)
            .filter(SpaceMembership.membership_id == member_membership_id)
            .one()
        )
        assert current_member.role == "space_admin"
        assert current_member.deleted_at is None


def test_concurrent_demote_and_user_deactivation_retain_space_admin(db_sessionmaker, monkeypatch):
    space_id, admin_memberships, _ = _seed_space_with_members(db_sessionmaker, admin_count=2)
    first_membership_id, second_membership_id = admin_memberships
    ctx = SpaceContext(
        space_id=space_id,
        space_name="Admin Guard Space",
        is_global_admin=False,
        space_role="space_admin",
    )
    actor = SimpleNamespace(user_id="concurrent-actor", role="user")
    first_has_lock = Event()
    release_first = Event()
    second_attempted_lock = Event()
    real_lock = user_admin_guards.lock_space_admin_spaces

    def lock_first_then_pause(session, space_ids):
        locked_spaces = real_lock(session, space_ids)
        first_has_lock.set()
        if not release_first.wait(timeout=10):
            raise AssertionError("Timed out waiting to release the first space-admin mutation")
        return locked_spaces

    def record_second_lock_attempt(session, space_ids):
        second_attempted_lock.set()
        return real_lock(session, space_ids)

    monkeypatch.setattr(spaces_routes, "lock_space_admin_spaces", lock_first_then_pause)
    monkeypatch.setattr(user_admin_guards, "lock_space_admin_spaces", record_second_lock_attempt)

    def demote_first_admin():
        with db_sessionmaker() as session:
            row = spaces_routes.update_space_member(
                space_id,
                first_membership_id,
                SpaceMembershipUpdate(role="member"),
                session=session,
                ctx=ctx,
            )
            return row.role

    def deactivate_second_admin():
        with db_sessionmaker() as session:
            try:
                users_routes.update_user(
                    "admin-user-1",
                    UserUpdate(is_active=False),
                    session=session,
                    space_ctx=ctx,
                    current_user=actor,
                    _authz=ctx,
                )
            except HTTPException as exc:
                session.rollback()
                return exc.status_code, exc.detail
            return 200, None

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(demote_first_admin)
        second_future = None
        try:
            assert first_has_lock.wait(timeout=10)
            second_future = executor.submit(deactivate_second_admin)
            assert second_attempted_lock.wait(timeout=10)
        finally:
            release_first.set()

        assert first_future.result(timeout=10) == "member"
        assert second_future is not None
        assert second_future.result(timeout=10) == (
            400,
            "Space must retain at least one active space_admin",
        )

    with db_sessionmaker() as session:
        active_admins = (
            session.query(SpaceMembership)
            .join(User, User.user_id == SpaceMembership.user_id)
            .filter(SpaceMembership.space_id == space_id)
            .filter(SpaceMembership.deleted_at.is_(None))
            .filter(SpaceMembership.status == "active")
            .filter(SpaceMembership.role == "space_admin")
            .filter(User.is_active)
            .all()
        )
        assert [row.membership_id for row in active_admins] == [second_membership_id]


@pytest.mark.anyio
async def test_space_member_cannot_toggle_public_program_dashboard(client, db_sessionmaker):
    space_id, _, _ = _seed_space_with_members(db_sessionmaker, admin_count=1, include_member=True)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="member")
        response = await client.patch(
            f"/project-manager/api/spaces/{space_id}",
            json={"public_program_dashboard_enabled": True},
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "Space admin required"
    finally:
        _restore_current_space_override(original_current_space)


@pytest.mark.anyio
async def test_global_admin_can_toggle_public_program_dashboard_for_any_space(client):
    created = await client.post(
        "/project-manager/api/spaces",
        json={"name": "Global Toggle Space", "slug": "global-toggle-space"},
    )
    assert created.status_code == 201, created.text
    space_id = created.json()["space_id"]

    response = await client.patch(
        f"/project-manager/api/spaces/{space_id}",
        json={"public_program_dashboard_enabled": True},
    )

    assert response.status_code == 200, response.text
    assert response.json()["public_program_dashboard_enabled"] is True


@pytest.mark.anyio
async def test_space_admin_cannot_rename_space_through_public_dashboard_toggle(client, db_sessionmaker):
    space_id, _, _ = _seed_space_with_members(db_sessionmaker, admin_count=1)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        _set_current_space_override(space_id, role="space_admin")
        response = await client.patch(
            f"/project-manager/api/spaces/{space_id}",
            json={"name": "Renamed By Space Admin", "public_program_dashboard_enabled": True},
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "Global admin required"
    finally:
        _restore_current_space_override(original_current_space)


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
async def test_archived_space_memberships_are_read_only_until_reactivated(client, db_sessionmaker):
    with db_sessionmaker() as session:
        archived_space = Space(
            space_id="archived-membership-space",
            name="Archived Membership Space",
            slug="archived-membership-space",
            is_active=False,
        )
        active_space = Space(
            space_id="active-membership-space",
            name="Active Membership Space",
            slug="active-membership-space",
            is_active=True,
        )
        target = User(
            user_id="archived-member-target",
            soeid="archtarget",
            email="archtarget@example.com",
            display_name="Archived Target",
            password_hash="x",
            role="user",
            is_active=True,
        )
        existing = User(
            user_id="archived-existing-target",
            soeid="archexisting",
            email="archexisting@example.com",
            display_name="Archived Existing",
            password_hash="x",
            role="user",
            is_active=True,
        )
        membership = SpaceMembership(
            membership_id="archived-existing-membership",
            space_id=archived_space.space_id,
            user_id=existing.user_id,
            role="member",
            status="active",
        )
        session.add_all([archived_space, active_space, target, existing, membership])
        session.commit()

    listed = await client.get("/project-manager/api/spaces/archived-membership-space/members")
    assert listed.status_code == 200, listed.text

    created = await client.post(
        "/project-manager/api/spaces/archived-membership-space/members/by-soeid",
        json={"soeid": "archtarget", "role": "member", "status": "active"},
    )
    assert created.status_code == 400, created.text
    assert created.json()["detail"] == "Reactivate the space before changing memberships"

    updated = await client.patch(
        "/project-manager/api/spaces/archived-membership-space/members/archived-existing-membership",
        json={"role": "space_admin"},
    )
    assert updated.status_code == 400, updated.text
    assert updated.json()["detail"] == "Reactivate the space before changing memberships"

    deleted = await client.delete(
        "/project-manager/api/spaces/archived-membership-space/members/archived-existing-membership",
    )
    assert deleted.status_code == 400, deleted.text
    assert deleted.json()["detail"] == "Reactivate the space before changing memberships"

    reactivated = await client.patch(
        "/project-manager/api/spaces/archived-membership-space",
        json={"is_active": True},
    )
    assert reactivated.status_code == 200, reactivated.text

    allowed = await client.post(
        "/project-manager/api/spaces/archived-membership-space/members/by-soeid",
        json={"soeid": "archtarget", "role": "member", "status": "active"},
    )
    assert allowed.status_code == 201, allowed.text


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
