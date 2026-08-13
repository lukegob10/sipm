from __future__ import annotations

from fastapi import HTTPException
import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from backend.app.models import AgentChangeRequest, Space, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_change_requests import create_change_request
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
