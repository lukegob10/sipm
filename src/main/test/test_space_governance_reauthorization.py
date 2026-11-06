from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import update

from backend.app.models import Space, SpaceAccessRequest, SpaceMembership, User
from backend.app.routes import spaces as routes
from backend.app.schemas import SpaceMembershipCreate, SpaceMembershipCreateBySoeid, SpaceMembershipUpdate
from backend.app.services.spaces import SpaceContext


def _seed(session, *, global_admin=False):
    session.add(Space(space_id="guard-space", name="Guard Space", slug="guard-space"))
    for user_id, role in (
        ("guard-actor", "global_admin" if global_admin else "user"),
        ("guard-backup", "user"), ("guard-target", "user"), ("guard-requester", "user"),
    ):
        session.add(User(
            user_id=user_id, soeid=user_id, email=f"{user_id}@example.com",
            display_name=user_id, password_hash="unused", role=role, is_active=True,
        ))
    session.add_all([
        SpaceMembership(
            membership_id="guard-actor-member", space_id="guard-space", user_id="guard-actor",
            role="member" if global_admin else "space_admin", status="active",
        ),
        SpaceMembership(
            membership_id="guard-backup-member", space_id="guard-space", user_id="guard-backup",
            role="space_admin", status="active",
        ),
        SpaceMembership(
            membership_id="guard-target-member", space_id="guard-space", user_id="guard-target",
            role="member", status="active",
        ),
        SpaceAccessRequest(
            request_id="guard-request", space_id="guard-space", requester_user_id="guard-requester",
            requested_role="member", status="pending",
        ),
    ])
    session.commit()


def _execute(action, session, actor, ctx):
    if action == "add":
        return routes.create_space_member(
            "guard-space", SpaceMembershipCreate(user_id="guard-requester"),
            session=session, ctx=ctx, current_user=actor,
        )
    if action == "add_by_soeid":
        return routes.create_space_member_by_soeid(
            "guard-space", SpaceMembershipCreateBySoeid(soeid="guard-requester"),
            session=session, ctx=ctx, current_user=actor,
        )
    if action == "update":
        return routes.update_space_member(
            "guard-space", "guard-target-member", SpaceMembershipUpdate(role="space_admin"),
            session=session, ctx=ctx, current_user=actor,
        )
    if action == "delete":
        return routes.delete_space_member(
            "guard-space", "guard-target-member", session=session, ctx=ctx, current_user=actor,
        )
    handler = routes.approve_space_access_request if action == "approve" else routes.reject_space_access_request
    return handler("guard-request", payload=None, session=session, ctx=ctx, current_user=actor)


@pytest.mark.parametrize("action", ["add", "add_by_soeid", "update", "delete", "approve", "reject"])
@pytest.mark.parametrize(
    "revocation",
    ["membership_demoted", "membership_inactive", "membership_deleted", "user_inactive", "global_demoted"],
)
def test_governance_rechecks_actor_after_waiting_for_space_lock(
    db_sessionmaker, monkeypatch, action, revocation,
):
    global_admin = revocation == "global_demoted"
    with db_sessionmaker() as session:
        _seed(session, global_admin=global_admin)

    original_lock = routes.lock_space_admin_spaces

    def revoke_before_lock(session, space_ids):
        if revocation.startswith("membership_"):
            changes = {
                "membership_demoted": {"role": "member"},
                "membership_inactive": {"status": "inactive"},
                "membership_deleted": {"deleted_at": datetime.now(timezone.utc)},
            }[revocation]
            session.execute(update(SpaceMembership).where(
                SpaceMembership.membership_id == "guard-actor-member"
            ).values(**changes), execution_options={"synchronize_session": False})
        else:
            changes = {"is_active": False} if revocation == "user_inactive" else {"role": "user"}
            session.execute(update(User).where(User.user_id == "guard-actor").values(**changes),
                            execution_options={"synchronize_session": False})
        return original_lock(session, space_ids)

    monkeypatch.setattr(routes, "lock_space_admin_spaces", revoke_before_lock)
    with db_sessionmaker() as session:
        actor = session.get(User, "guard-actor")
        ctx = SpaceContext(
            space_id="guard-space", space_name="Guard Space", is_global_admin=global_admin,
            space_role="space_admin",
        )
        with pytest.raises(HTTPException) as denied:
            _execute(action, session, actor, ctx)
        assert denied.value.status_code == 403
        session.rollback()

    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "guard-request").status == "pending"
        target = session.get(SpaceMembership, "guard-target-member")
        assert target.role == "member" and target.deleted_at is None
        assert session.query(SpaceMembership).filter_by(
            space_id="guard-space", user_id="guard-requester"
        ).count() == 0
