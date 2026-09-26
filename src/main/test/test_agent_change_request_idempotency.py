from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from backend.app.models import AgentChangeRequest, Project, Space, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_change_requests import (
    approve_change_request,
    approve_change_request_operations,
    approve_selected_change_requests,
    create_change_request,
    reject_selected_change_requests,
)
from backend.app.services.spaces import SpaceContext


def _seed_actor(db_sessionmaker) -> tuple[str, str]:
    space_id = "idempotency-space"
    user_id = "idempotency-agent"
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(space_id=space_id, name="Idempotency Space", slug=space_id),
                User(
                    user_id=user_id,
                    soeid="idempotency-agent",
                    email="idempotency-agent@example.com",
                    display_name="Idempotency Agent",
                    password_hash="unused",
                    role="user",
                    is_active=True,
                    is_service_account=True,
                ),
            ]
        )
        session.commit()
    return user_id, space_id


def _request(*, reason: str = "create once", idempotency_key: str = "same-key"):
    return AgentPatchRequest(
        dry_run=False,
        reason=reason,
        idempotency_key=idempotency_key,
        operations=[
            {
                "client_operation_id": "create-project",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Created Once", "status": "active"},
            }
        ],
    )


def _space_context(space_id: str) -> SpaceContext:
    return SpaceContext(
        space_id=space_id,
        space_name="Idempotency Space",
        space_role="member",
        is_global_admin=False,
    )


def _insert_concurrent_winner(
    db_sessionmaker,
    *,
    winner_id: str,
    winner_reason: str | None = None,
):
    def insert_winner(session, _flush_context, _instances) -> None:
        pending = next(
            row for row in session.new if isinstance(row, AgentChangeRequest)
        )
        with db_sessionmaker() as concurrent_session:
            concurrent_session.add(
                AgentChangeRequest(
                    change_request_id=winner_id,
                    space_id=pending.space_id,
                    proposed_by_user_id=pending.proposed_by_user_id,
                    status=pending.status,
                    reason=winner_reason or pending.reason,
                    idempotency_key=pending.idempotency_key,
                    operations_json=pending.operations_json,
                    validation_json=pending.validation_json,
                    diff_json=pending.diff_json,
                )
            )
            concurrent_session.commit()

    return insert_winner


def test_concurrent_identical_submission_returns_database_winner(db_sessionmaker):
    user_id, space_id = _seed_actor(db_sessionmaker)
    with db_sessionmaker() as session:
        user = session.get(User, user_id)
        event.listen(
            session,
            "before_flush",
            _insert_concurrent_winner(
                db_sessionmaker,
                winner_id="concurrent-winner",
            ),
            once=True,
        )

        result = create_change_request(
            session,
            _space_context(space_id),
            user,
            _request(),
        )

    assert result.change_request_id == "concurrent-winner"
    with db_sessionmaker() as session:
        assert session.query(AgentChangeRequest).count() == 1


def test_concurrent_different_submission_preserves_idempotency_conflict(
    db_sessionmaker,
):
    user_id, space_id = _seed_actor(db_sessionmaker)
    with db_sessionmaker() as session:
        user = session.get(User, user_id)
        event.listen(
            session,
            "before_flush",
            _insert_concurrent_winner(
                db_sessionmaker,
                winner_id="concurrent-conflict",
                winner_reason="different request",
            ),
            once=True,
        )

        with pytest.raises(HTTPException) as exc_info:
            create_change_request(
                session,
                _space_context(space_id),
                user,
                _request(),
            )

    assert exc_info.value.status_code == 409
    assert (
        exc_info.value.detail
        == "idempotency_key has already been used with a different request"
    )
    with db_sessionmaker() as session:
        assert session.query(AgentChangeRequest).count() == 1


def test_unrelated_integrity_error_is_not_misreported_as_idempotent_retry(
    db_sessionmaker,
):
    user_id, space_id = _seed_actor(db_sessionmaker)
    with db_sessionmaker() as session:
        session.add(
            AgentChangeRequest(
                change_request_id="occupied-request-id",
                space_id=space_id,
                proposed_by_user_id=user_id,
                status="pending",
                reason="existing request",
                idempotency_key="existing-key",
                operations_json="[]",
                validation_json="{}",
                diff_json="[]",
            )
        )
        session.commit()

    def reuse_primary_key(session, _flush_context, _instances) -> None:
        pending = next(
            row for row in session.new if isinstance(row, AgentChangeRequest)
        )
        pending.change_request_id = "occupied-request-id"

    with db_sessionmaker() as session:
        user = session.get(User, user_id)
        event.listen(session, "before_flush", reuse_primary_key, once=True)

        with pytest.raises(IntegrityError):
            create_change_request(
                session,
                _space_context(space_id),
                user,
                _request(idempotency_key="new-key"),
            )

    with db_sessionmaker() as session:
        assert session.query(AgentChangeRequest).count() == 1


@pytest.mark.parametrize(
    "approve_selected", [False, True], ids=["whole-request", "selected-operations"]
)
def test_change_request_approval_rolls_back_patch_if_final_commit_fails(
    db_sessionmaker, monkeypatch, approve_selected
):
    user_id, space_id = _seed_actor(db_sessionmaker)
    monkeypatch.setattr(
        "backend.app.services.agent_change_requests._publish_change_requests",
        lambda _space_id: None,
    )
    monkeypatch.setattr(
        "backend.app.services.agent_patch_plan.publish_space_mutation",
        lambda *_args, **_kwargs: None,
    )
    with db_sessionmaker() as session:
        agent = session.get(User, user_id)
        request = create_change_request(
            session, _space_context(space_id), agent, _request()
        )
        reviewer = User(
            user_id="atomic-reviewer",
            soeid="atomic-reviewer",
            email="atomic-reviewer@example.com",
            display_name="Atomic Reviewer",
            password_hash="unused",
            role="user",
            is_active=True,
            is_service_account=False,
        )
        session.add(reviewer)
        session.commit()

    def fail_when_request_is_approved(session, _flush_context, _instances):
        if any(
            isinstance(row, AgentChangeRequest) and row.status == "approved"
            for row in session.dirty
        ):
            raise RuntimeError("simulated approval status commit failure")

    with db_sessionmaker() as session:
        event.listen(session, "before_flush", fail_when_request_is_approved)
        try:
            with pytest.raises(
                RuntimeError, match="simulated approval status commit failure"
            ):
                if approve_selected:
                    approve_change_request_operations(
                        session,
                        _space_context(space_id),
                        session.get(User, "atomic-reviewer"),
                        request.change_request_id,
                        ["create-project"],
                    )
                else:
                    approve_change_request(
                        session,
                        _space_context(space_id),
                        session.get(User, "atomic-reviewer"),
                        request.change_request_id,
                    )
        finally:
            event.remove(session, "before_flush", fail_when_request_is_approved)

    with db_sessionmaker() as session:
        stored_request = session.get(AgentChangeRequest, request.change_request_id)
        assert stored_request.status == "pending"
        assert (
            session.query(Project)
            .filter(Project.project_name == "Created Once")
            .first()
            is None
        )


def test_change_request_publishes_applied_mutations_after_outer_commit(
    db_sessionmaker, monkeypatch
):
    user_id, space_id = _seed_actor(db_sessionmaker)
    with db_sessionmaker() as session:
        agent = session.get(User, user_id)
        request = create_change_request(
            session, _space_context(space_id), agent, _request()
        )
        reviewer = User(
            user_id="publish-reviewer",
            soeid="publish-reviewer",
            email="publish-reviewer@example.com",
            display_name="Publish Reviewer",
            password_hash="unused",
            role="user",
            is_active=True,
            is_service_account=False,
        )
        session.add(reviewer)
        session.commit()

    publications: list[str] = []

    def assert_committed(space_id_arg, cache_keys, *, broadcast_channel=None):
        assert space_id_arg == space_id
        assert broadcast_channel in cache_keys
        with db_sessionmaker() as session:
            stored_request = session.get(AgentChangeRequest, request.change_request_id)
            assert stored_request.status == "approved"
            assert (
                session.query(Project)
                .filter(Project.project_name == "Created Once")
                .first()
                is not None
            )
        publications.append(broadcast_channel)

    monkeypatch.setattr(
        "backend.app.services.agent_patch_plan.publish_space_mutation",
        assert_committed,
    )
    monkeypatch.setattr(
        "backend.app.services.agent_change_requests._publish_change_requests",
        lambda _space_id: publications.append("agent_change_requests"),
    )
    with db_sessionmaker() as session:
        result = approve_change_request(
            session,
            _space_context(space_id),
            session.get(User, "publish-reviewer"),
            request.change_request_id,
        )

    assert result.status == "approved"
    assert publications == ["projects", "solutions", "tasks", "agent_change_requests"]


def test_apply_flush_integrity_error_commits_failed_request_without_patch(
    db_sessionmaker, monkeypatch
):
    user_id, space_id = _seed_actor(db_sessionmaker)
    monkeypatch.setattr(
        "backend.app.services.agent_change_requests._publish_change_requests",
        lambda _space_id: None,
    )
    monkeypatch.setattr(
        "backend.app.services.agent_patch_plan.publish_space_mutation",
        lambda *_args, **_kwargs: None,
    )
    with db_sessionmaker() as session:
        request = create_change_request(
            session,
            _space_context(space_id),
            session.get(User, user_id),
            _request(),
        )
        reviewer = User(
            user_id="flush-reviewer",
            soeid="flush-reviewer",
            email="flush-reviewer@example.com",
            display_name="Flush Reviewer",
            password_hash="unused",
            role="user",
            is_active=True,
            is_service_account=False,
        )
        session.add(reviewer)
        session.commit()

    def fail_project_insert(session, _flush_context, _instances):
        if any(
            isinstance(row, Project) and row.project_name == "Created Once"
            for row in session.new
        ):
            raise IntegrityError("simulated project conflict", {}, RuntimeError())

    with db_sessionmaker() as session:
        event.listen(session, "before_flush", fail_project_insert)
        try:
            result = approve_change_request(
                session,
                _space_context(space_id),
                session.get(User, "flush-reviewer"),
                request.change_request_id,
            )
        finally:
            event.remove(session, "before_flush", fail_project_insert)

    assert result.status == "failed"
    with db_sessionmaker() as session:
        stored_request = session.get(AgentChangeRequest, request.change_request_id)
        assert stored_request.status == "failed"
        assert stored_request.reviewed_by_user_id == "flush-reviewer"
        assert stored_request.reviewed_at is not None
        assert (
            session.query(Project)
            .filter(Project.project_name == "Created Once")
            .first()
            is None
        )


def test_bulk_review_rejects_duplicate_ids_before_transition(db_sessionmaker):
    user_id, space_id = _seed_actor(db_sessionmaker)
    with db_sessionmaker() as session:
        agent = session.get(User, user_id)
        request = create_change_request(
            session, _space_context(space_id), agent, _request()
        )
        reviewer = User(
            user_id="bulk-reviewer",
            soeid="bulk-reviewer",
            email="bulk-reviewer@example.com",
            display_name="Bulk Reviewer",
            password_hash="unused",
            role="user",
            is_active=True,
            is_service_account=False,
        )
        session.add(reviewer)
        session.commit()

    with db_sessionmaker() as session:
        reviewer = session.get(User, "bulk-reviewer")
        for review in (
            approve_selected_change_requests,
            reject_selected_change_requests,
        ):
            with pytest.raises(HTTPException) as exc_info:
                review(
                    session,
                    _space_context(space_id),
                    reviewer,
                    [request.change_request_id, request.change_request_id],
                )
            assert exc_info.value.status_code == 400

        stored_request = session.get(AgentChangeRequest, request.change_request_id)
        assert stored_request.status == "pending"
