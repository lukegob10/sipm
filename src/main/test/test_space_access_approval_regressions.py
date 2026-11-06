from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier, Event, local

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from backend.app.models import Space, SpaceAccessRequest, SpaceMembership, User
from backend.app.routes import spaces as space_routes
from backend.app.routes.spaces import approve_space_access_request
from backend.app.schemas import SpaceMembershipUpdate
from backend.app.services.spaces import SpaceContext


def _seed_pending_request(session, *, existing_admin=False):
    requester = User(
        user_id="approval-requester", soeid="requester", email="requester@example.com",
        display_name="Requester", password_hash="unused", role="user", is_active=True,
    )
    reviewer = User(
        user_id="approval-reviewer", soeid="reviewer", email="reviewer@example.com",
        display_name="Reviewer", password_hash="unused", role="global_admin", is_active=True,
    )
    space = Space(
        space_id="approval-space", name="Approval Space", slug="approval-space",
        is_active=True, space_kind="collaboration",
    )
    request = SpaceAccessRequest(
        request_id="approval-request", space_id=space.space_id,
        requester_user_id=requester.user_id, requested_role="member", status="pending",
    )
    session.add_all([requester, reviewer, space, request])
    if existing_admin:
        session.add(SpaceMembership(
            membership_id="approval-membership", space_id=space.space_id,
            user_id=requester.user_id, role="space_admin", status="active",
        ))
    session.commit()


def _approve(session, *, global_admin=True):
    reviewer = session.get(User, "approval-reviewer")
    return approve_space_access_request(
        "approval-request",
        payload=None,
        session=session,
        current_user=reviewer,
        ctx=SpaceContext(
            space_id="approval-space", space_name="Approval Space",
            is_global_admin=global_admin, space_role="space_admin",
        ),
    )


def test_approving_stale_request_does_not_demote_existing_space_admin(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed_pending_request(session, existing_admin=True)
        _approve(session)

    with db_sessionmaker() as session:
        membership = session.get(SpaceMembership, "approval-membership")
        assert membership.role == "space_admin"
        assert membership.status == "active"


def test_approval_failure_rolls_back_membership_and_request_together(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed_pending_request(session)

    with db_sessionmaker() as session:
        def fail_approval_flush(session, _context, _instances):
            if any(
                isinstance(row, SpaceMembership) for row in session.new
            ):
                raise RuntimeError("injected approval failure")

        event.listen(session, "before_flush", fail_approval_flush)
        with pytest.raises(RuntimeError, match="injected approval failure"):
            _approve(session)
        session.rollback()

    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "approval-request").status == "pending"
        assert session.query(SpaceMembership).filter_by(
            space_id="approval-space", user_id="approval-requester"
        ).count() == 0


@pytest.mark.parametrize(
    "state, status, detail",
    [("archived", 400, "Space is archived"), ("deleted", 404, "Space not found")],
)
def test_approval_retains_unavailable_space_errors(db_sessionmaker, state, status, detail):
    with db_sessionmaker() as session:
        _seed_pending_request(session)
        space = session.get(Space, "approval-space")
        if state == "archived":
            space.is_active = False
        else:
            space.deleted_at = datetime.now(timezone.utc)
        session.commit()
        with pytest.raises(HTTPException) as error:
            _approve(session)
        assert error.value.status_code == status
        assert error.value.detail == detail

    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "approval-request").status == "pending"
        assert session.query(SpaceMembership).filter_by(space_id="approval-space").count() == 0


def test_approval_rechecks_space_state_after_lock(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        _seed_pending_request(session)

    original_lock = space_routes.lock_space_admin_spaces

    def archive_before_lock(session, space_ids):
        session.query(Space).filter_by(space_id="approval-space").update(
            {Space.is_active: False}, synchronize_session=False,
        )
        return original_lock(session, space_ids)

    monkeypatch.setattr(space_routes, "lock_space_admin_spaces", archive_before_lock)
    with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as error:
            _approve(session)
        assert error.value.status_code == 400
        assert error.value.detail == "Space is archived"
        session.rollback()

    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "approval-request").status == "pending"
        assert session.query(SpaceMembership).filter_by(space_id="approval-space").count() == 0


def test_approval_rechecks_requester_after_global_lock(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        _seed_pending_request(session)
    original_lock = space_routes.lock_global_admin_users

    def deactivate_before_lock(session):
        session.query(User).filter_by(user_id="approval-requester").update(
            {User.is_active: False}, synchronize_session=False,
        )
        return original_lock(session)

    monkeypatch.setattr(space_routes, "lock_global_admin_users", deactivate_before_lock)
    with db_sessionmaker() as session:
        with pytest.raises(HTTPException) as error:
            _approve(session)
        assert error.value.status_code == 400
        assert error.value.detail == "Requester is not active"
        session.rollback()

    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "approval-request").status == "pending"
        assert session.query(SpaceMembership).filter_by(space_id="approval-space").count() == 0


@pytest.mark.parametrize("competing_decision", ["reject", "cancel"])
def test_simultaneous_decisions_have_only_one_winner(db_sessionmaker, competing_decision):
    with db_sessionmaker() as session:
        _seed_pending_request(session)
        session.get(User, "approval-reviewer").role = "user"
        session.add(SpaceMembership(
            space_id="approval-space", user_id="approval-reviewer", role="space_admin", status="active",
        ))
        session.commit()

    barrier = Barrier(2, timeout=5)
    engine = db_sessionmaker.kw["bind"]

    def synchronize_updates(_conn, _cursor, statement, _params, _context, _many):
        if (statement.lstrip().upper().startswith("UPDATE")
                and SpaceAccessRequest.__tablename__.lower() in statement.lower()):
            barrier.wait()

    event.listen(engine, "before_cursor_execute", synchronize_updates)

    def decide(action):
        with db_sessionmaker() as session:
            actor_id = "approval-requester" if action == "cancel" else "approval-reviewer"
            actor = session.get(User, actor_id)
            ctx = SpaceContext(
                space_id="approval-space", space_name="Approval Space",
                is_global_admin=False, space_role="space_admin",
            )
            try:
                if action == "cancel":
                    result = space_routes.cancel_space_access_request(
                        "approval-request", session=session, current_user=actor, _ctx=ctx,
                    )
                else:
                    handler = (space_routes.approve_space_access_request if action == "approve"
                               else space_routes.reject_space_access_request)
                    result = handler(
                        "approval-request", payload=None, session=session, current_user=actor, ctx=ctx,
                    )
            except HTTPException as exc:
                return exc.status_code, None
            return 200, result.status

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(decide, action) for action in ("approve", competing_decision)]
            results = [future.result(timeout=10) for future in futures]
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_updates)

    assert sorted(status for status, _ in results) == [200, 400]
    winner = next(decision for status, decision in results if status == 200)
    with db_sessionmaker() as session:
        assert session.get(SpaceAccessRequest, "approval-request").status == winner
        membership_count = session.query(SpaceMembership).filter_by(
            space_id="approval-space", user_id="approval-requester"
        ).count()
        assert membership_count == (1 if winner == "approved" else 0)


def test_approval_serializes_with_membership_promotion(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        _seed_pending_request(session)
        session.get(User, "approval-reviewer").role = "user"
        session.add(SpaceMembership(
            space_id="approval-space", user_id="approval-reviewer", role="space_admin", status="active",
        ))
        session.add(SpaceMembership(
            membership_id="approval-membership", space_id="approval-space",
            user_id="approval-requester", role="member", status="inactive",
        ))
        session.commit()

    approval_in_membership = Event()
    approval_space_locked = Event()
    promotion_entered_lock = Event()
    allow_approval = Event()
    thread_state = local()
    original_ensure = space_routes.ensure_space_membership
    original_lock = space_routes.lock_space_admin_spaces

    def controlled_ensure(*args, **kwargs):
        approval_in_membership.set()
        assert allow_approval.wait(5)
        return original_ensure(*args, **kwargs)

    def observed_space_lock(*args, **kwargs):
        if getattr(thread_state, "approval", False):
            result = original_lock(*args, **kwargs)
            approval_space_locked.set()
            return result
        promotion_entered_lock.set()
        return original_lock(*args, **kwargs)

    monkeypatch.setattr(space_routes, "ensure_space_membership", controlled_ensure)
    monkeypatch.setattr(space_routes, "lock_space_admin_spaces", observed_space_lock)

    def approve():
        thread_state.approval = True
        with db_sessionmaker() as session:
            return _approve(session, global_admin=False).status

    def promote():
        with db_sessionmaker() as session:
            return space_routes.update_space_member(
                "approval-space", "approval-membership",
                SpaceMembershipUpdate(role="space_admin", status="active"),
                session=session,
                current_user=session.get(User, "approval-reviewer"),
                ctx=SpaceContext(
                    space_id="approval-space", space_name="Approval Space",
                    is_global_admin=False, space_role="space_admin",
                ),
            ).role

    with ThreadPoolExecutor(max_workers=2) as executor:
        approval = executor.submit(approve)
        try:
            assert approval_in_membership.wait(5)
            promotion = executor.submit(promote)
            assert promotion_entered_lock.wait(5)
            assert not promotion.done()
        finally:
            allow_approval.set()
        assert approval.result(timeout=10) == "approved"
        assert promotion.result(timeout=10) == "space_admin"

    assert approval_space_locked.is_set()
    with db_sessionmaker() as session:
        assert session.get(SpaceMembership, "approval-membership").role == "space_admin"
