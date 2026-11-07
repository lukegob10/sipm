from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import spaces as routes
from backend.app.schemas import PersonalSpaceCreate, SpaceMembershipUpdate
from backend.app.services.spaces import SpaceContext, resolve_active_space_context


def _user(user_id):
    return User(
        user_id=user_id, soeid=user_id, email=f"{user_id}@example.com",
        display_name=user_id, password_hash="unused", role="user", is_active=True,
    )


@pytest.mark.parametrize("collision_state", ["active", "archived", "deleted"])
def test_personal_space_skips_all_reserved_generated_identifiers(db_sessionmaker, collision_state):
    now = datetime.now(timezone.utc)
    with db_sessionmaker() as session:
        owner = _user("healthowner")
        session.add(owner)
        for suffix in ("", " 2"):
            session.add(Space(
                space_id=f"reserved{suffix.strip()}", name=f"HEALTHOWNER Personal{suffix}",
                slug=f"healthowner-personal{'-2' if suffix else ''}", space_kind="collaboration",
                is_active=collision_state != "archived",
                archived_at=now if collision_state == "archived" else None,
                deleted_at=now if collision_state == "deleted" else None,
            ))
        session.commit()

        ctx = SpaceContext("home", "Home", False, "member", space_kind="lobby")
        created = routes.create_personal_space(
            PersonalSpaceCreate(), session=session, current_user=owner, _ctx=ctx,
        )
        assert created.name == "HEALTHOWNER Personal 3"
        assert created.slug == "healthowner-personal-3"
        assert created.owner_user_id == owner.user_id
        membership = session.query(SpaceMembership).filter_by(space_id=created.space_id).one()
        assert (membership.user_id, membership.role, membership.status) == (owner.user_id, "space_admin", "active")
        assert session.query(Space).count() == 3
        reserved = session.get(Space, "reserved")
        assert (reserved.deleted_at is not None) == (collision_state == "deleted")
        assert reserved.is_active == (collision_state != "archived")

        with pytest.raises(HTTPException) as duplicate:
            routes.create_personal_space(
                PersonalSpaceCreate(), session=session, current_user=owner, _ctx=ctx,
            )
        assert duplicate.value.status_code == 400
        assert duplicate.value.detail == "User already has a personal space"
        assert session.query(SpaceMembership).count() == 1


def _seed_admins(session, *, backup_role, backup_state="active"):
    actor = _user("healthactor")
    backup = _user("healthbackup")
    backup.is_active = backup_state != "inactive_user"
    session.add_all([
        actor, backup, Space(space_id="healthspace", name="Health Space", slug="healthspace"),
        SpaceMembership(
            membership_id="healthactor-membership", space_id="healthspace", user_id=actor.user_id,
            role="space_admin", status="active",
        ),
        SpaceMembership(
            membership_id="healthbackup-membership", space_id="healthspace", user_id=backup.user_id,
            role=backup_role, status="inactive" if backup_state == "inactive_member" else "active",
            deleted_at=datetime.now(timezone.utc) if backup_state == "deleted_member" else None,
        ),
    ])
    session.commit()
    return actor, backup


def _remove_admin(session, actor, ctx, action):
    if action == "delete":
        routes.delete_space_member(
            "healthspace", "healthactor-membership", session=session, current_user=actor, ctx=ctx,
        )
    else:
        payload = SpaceMembershipUpdate(role="member") if action == "demote" else SpaceMembershipUpdate(status="inactive")
        routes.update_space_member(
            "healthspace", "healthactor-membership", payload, session=session, current_user=actor, ctx=ctx,
        )


@pytest.mark.parametrize("backup_role", [" Space Admin ", " SPACE-ADMIN ", " space_admin "])
@pytest.mark.parametrize("action", ["demote", "deactivate", "delete"])
def test_accepted_padded_admin_roles_count_as_remaining_admins(db_sessionmaker, backup_role, action):
    with db_sessionmaker() as session:
        actor, backup = _seed_admins(session, backup_role=backup_role)
        assert resolve_active_space_context(session, backup, "healthspace").space_role == "space_admin"
        ctx = resolve_active_space_context(session, actor, "healthspace")
        _remove_admin(session, actor, ctx, action)

    with db_sessionmaker() as session:
        row = session.get(SpaceMembership, "healthactor-membership")
        if action == "demote":
            assert row.role == "member"
        elif action == "deactivate":
            assert row.status == "inactive"
        else:
            assert row.deleted_at is not None
        assert session.get(SpaceMembership, "healthbackup-membership").role == backup_role


@pytest.mark.parametrize("backup_state", ["inactive_user", "inactive_member", "deleted_member"])
def test_unavailable_padded_admin_does_not_allow_removing_last_admin(db_sessionmaker, backup_state):
    with db_sessionmaker() as session:
        actor, _ = _seed_admins(session, backup_role=" Space Admin ", backup_state=backup_state)
        ctx = resolve_active_space_context(session, actor, "healthspace")
        with pytest.raises(HTTPException) as denied:
            _remove_admin(session, actor, ctx, "demote")
        assert denied.value.status_code == 400
        assert denied.value.detail == "Space must retain at least one active space_admin"
        session.rollback()

    with db_sessionmaker() as session:
        row = session.get(SpaceMembership, "healthactor-membership")
        assert (row.role, row.status, row.deleted_at) == ("space_admin", "active", None)
