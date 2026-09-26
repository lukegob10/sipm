from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import event
from starlette.requests import Request

from backend.app.auth import auth as auth_module
from backend.app.auth.auth import SESSION_IDLE_MINUTES, hash_password, verify_password
from backend.app.deps import authenticate_access_token_context, require_human_delegated_token
from backend.app.models import AuthSession, User
from backend.app.services import auth_sessions as auth_sessions_module
from backend.app.services import password_reset as password_reset_module
from backend.app.services.auth_sessions import require_auth_session


def _token_at(user_id: str, session_id: str, token_type: str, issued_at: datetime) -> str:
    return jwt.encode(
        {
            "sub": user_id,
            "role": "user",
            "type": token_type,
            "iat": int(issued_at.timestamp()),
            "exp": int((issued_at + timedelta(minutes=5)).timestamp()),
            "sid": session_id,
        },
        auth_module.SECRET_KEY,
        algorithm=auth_module.ALGORITHM,
    )


def _create_user_with_sessions(db_sessionmaker, *, force_password_reset: bool = False):
    now = datetime.now(timezone.utc)
    revoked_at = now.replace(tzinfo=None) - timedelta(minutes=1)
    with db_sessionmaker() as session:
        user = User(
            soeid="session-regression-user",
            email="session-regression-user@example.com",
            display_name="Session Regression User",
            password_hash=hash_password("OldPassword123"),
            role="user",
            is_active=True,
            force_password_reset=force_password_reset,
            temp_password_hash=(
                hash_password("TempPassword123") if force_password_reset else None
            ),
            temp_password_expires_at=(
                now + timedelta(minutes=15) if force_password_reset else None
            ),
        )
        session.add(user)
        session.flush()
        active_session = AuthSession(user_id=user.user_id)
        revoked_session = AuthSession(user_id=user.user_id, revoked_at=revoked_at)
        other_user = User(
            soeid="session-regression-other-user",
            email="session-regression-other-user@example.com",
            display_name="Other Session User",
            password_hash=hash_password("OtherPassword123"),
            role="user",
            is_active=True,
        )
        session.add(other_user)
        session.flush()
        other_user_session = AuthSession(user_id=other_user.user_id)
        session.add_all([active_session, revoked_session, other_user_session])
        session.commit()
        return (
            user.user_id,
            active_session.session_id,
            revoked_session.session_id,
            revoked_at,
            other_user_session.session_id,
        )


def test_record_activity_returns_deadline_without_followup_session_read(
    db_sessionmaker, monkeypatch
):
    user_id, session_id, _, _, _ = _create_user_with_sessions(db_sessionmaker)
    fixed_now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1)
    monkeypatch.setattr(auth_sessions_module, "utcnow_naive", lambda: fixed_now)

    with db_sessionmaker() as session:
        auth_session = session.query(AuthSession).filter_by(session_id=session_id).one()
        statements = []

        def capture_statement(_conn, _cursor, statement, _params, _context, _many):
            if AuthSession.__tablename__ in statement:
                statements.append(statement.lstrip().split(None, 1)[0].upper())

        event.listen(session.get_bind(), "before_cursor_execute", capture_statement)
        try:
            idle_expires_at = auth_sessions_module.record_activity(session, auth_session)
        finally:
            event.remove(session.get_bind(), "before_cursor_execute", capture_statement)

        assert idle_expires_at == fixed_now + timedelta(minutes=SESSION_IDLE_MINUTES)
        assert statements == ["UPDATE"]
        assert session.query(AuthSession).filter_by(session_id=session_id).one().last_activity_at == fixed_now
        assert session.query(AuthSession).filter_by(session_id=session_id).one().user_id == user_id


@pytest.mark.parametrize(
    ("state", "expected_error"),
    (("revoked", "SESSION_REVOKED"), ("idle_expired", "SESSION_IDLE_EXPIRED")),
)
def test_record_activity_cannot_revive_revoked_or_idle_expired_session(
    db_sessionmaker, monkeypatch, state, expected_error
):
    _, session_id, _, _, _ = _create_user_with_sessions(db_sessionmaker)
    with db_sessionmaker() as session:
        stale_session = session.query(AuthSession).filter_by(session_id=session_id).one()

    fixed_now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=1)
    monkeypatch.setattr(auth_sessions_module, "utcnow_naive", lambda: fixed_now)
    with db_sessionmaker() as session:
        if state == "revoked":
            session.query(AuthSession).filter_by(session_id=session_id).update(
                {AuthSession.revoked_at: fixed_now}, synchronize_session=False
            )
        else:
            session.query(AuthSession).filter_by(session_id=session_id).update(
                {
                    AuthSession.last_activity_at: fixed_now
                    - timedelta(minutes=SESSION_IDLE_MINUTES + 1)
                },
                synchronize_session=False,
            )
        session.commit()

    with db_sessionmaker() as session:
        persisted_before = session.query(AuthSession).filter_by(session_id=session_id).one()
        old_activity = persisted_before.last_activity_at
        with pytest.raises(HTTPException) as exc_info:
            auth_sessions_module.record_activity(session, stale_session)
        assert exc_info.value.status_code == 401
        assert exc_info.value.headers["X-Error-Code"] == expected_error

        persisted_after = session.query(AuthSession).filter_by(session_id=session_id).one()
        assert persisted_after.last_activity_at == old_activity
        if state == "revoked":
            assert persisted_after.revoked_at == fixed_now
        else:
            assert persisted_after.revoked_at is None


def test_issuing_temp_password_revokes_all_active_sessions(db_sessionmaker):
    (
        user_id,
        active_session_id,
        already_revoked_id,
        previously_revoked_at,
        other_session_id,
    ) = _create_user_with_sessions(db_sessionmaker)
    with db_sessionmaker() as session:
        user = session.query(User).filter_by(user_id=user_id).one()
        statement_tables = []

        def capture_statement(_conn, _cursor, statement, _params, _context, _many):
            if User.__tablename__ in statement:
                statement_tables.append("user")
            elif AuthSession.__tablename__ in statement:
                statement_tables.append("session")

        event.listen(session.get_bind(), "before_cursor_execute", capture_statement)
        try:
            password_reset_module.issue_temp_password(
                session,
                target_user=user,
                issued_by_user_id="admin-user",
            )
        finally:
            event.remove(session.get_bind(), "before_cursor_execute", capture_statement)

        active = session.query(AuthSession).filter_by(session_id=active_session_id).one()
        already_revoked = session.query(AuthSession).filter_by(session_id=already_revoked_id).one()
        other_user_session = session.query(AuthSession).filter_by(session_id=other_session_id).one()
        assert active.revoked_at is not None
        assert already_revoked.revoked_at == previously_revoked_at
        assert other_user_session.revoked_at is None
        assert statement_tables.index("user") < statement_tables.index("session")
        with pytest.raises(HTTPException) as exc_info:
            require_auth_session(session, {"sid": active_session_id}, user_id=user_id)
        assert exc_info.value.status_code == 401


def test_temp_password_issue_revokes_same_second_access_and_delegated_tokens(
    db_sessionmaker, monkeypatch
):
    user_id, session_id, _, _, _ = _create_user_with_sessions(db_sessionmaker)
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    access_token = _token_at(user_id, session_id, "access", issued_at)
    delegated_token = _token_at(user_id, session_id, "delegated", issued_at)

    class FixedDateTime:
        @staticmethod
        def now(_tz=None):
            return issued_at

    monkeypatch.setattr(password_reset_module, "datetime", FixedDateTime)
    with db_sessionmaker() as session:
        user = session.query(User).filter_by(user_id=user_id).one()
        password_reset_module.issue_temp_password(
            session,
            target_user=user,
            issued_by_user_id="admin-user",
        )

        # The iat and password_changed_at match to the second; session
        # revocation must reject both token types despite the skew grace.
        with pytest.raises(HTTPException) as access_error:
            authenticate_access_token_context(session, access_token)
        assert access_error.value.status_code == 401

        delegated_request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/delegated-review",
                "headers": [(b"authorization", f"Bearer {delegated_token}".encode())],
            }
        )
        with pytest.raises(HTTPException) as delegated_error:
            require_human_delegated_token(delegated_request, session)
        assert delegated_error.value.status_code == 401


def test_successful_temp_password_reset_revokes_all_active_sessions(db_sessionmaker):
    (
        user_id,
        active_session_id,
        already_revoked_id,
        previously_revoked_at,
        other_session_id,
    ) = _create_user_with_sessions(db_sessionmaker, force_password_reset=True)
    with db_sessionmaker() as session:
        password_reset_module.reset_password_with_temp_password(
            session,
            soeid="SESSION-REGRESSION-USER",
            temp_password="TempPassword123",
            new_password="ReplacementPassword123",
        )

        user = session.query(User).filter_by(user_id=user_id).one()
        active = session.query(AuthSession).filter_by(session_id=active_session_id).one()
        already_revoked = session.query(AuthSession).filter_by(session_id=already_revoked_id).one()
        other_user_session = session.query(AuthSession).filter_by(session_id=other_session_id).one()
        assert verify_password("ReplacementPassword123", user.password_hash)
        assert user.temp_password_hash is None
        assert active.revoked_at is not None
        assert already_revoked.revoked_at == previously_revoked_at
        assert other_user_session.revoked_at is None
        with pytest.raises(HTTPException) as exc_info:
            require_auth_session(session, {"sid": active_session_id}, user_id=user_id)
        assert exc_info.value.status_code == 401


def test_issuing_temp_password_rolls_back_user_and_session_changes_if_audit_fails(
    db_sessionmaker, monkeypatch
):
    user_id, active_session_id, _, _, _ = _create_user_with_sessions(db_sessionmaker)

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(password_reset_module, "log_changes", fail_audit)
    with db_sessionmaker() as session:
        user = session.query(User).filter_by(user_id=user_id).one()
        with pytest.raises(RuntimeError, match="audit unavailable"):
            password_reset_module.issue_temp_password(
                session,
                target_user=user,
                issued_by_user_id="admin-user",
            )

        persisted_user = session.query(User).filter_by(user_id=user_id).one()
        active = session.query(AuthSession).filter_by(session_id=active_session_id).one()
        assert persisted_user.force_password_reset is False
        assert persisted_user.temp_password_hash is None
        assert active.revoked_at is None


def test_completing_temp_password_reset_rolls_back_if_audit_fails(
    db_sessionmaker, monkeypatch
):
    user_id, active_session_id, _, _, _ = _create_user_with_sessions(
        db_sessionmaker,
        force_password_reset=True,
    )

    def fail_audit(*_args, **_kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(password_reset_module, "log_changes", fail_audit)
    with db_sessionmaker() as session:
        user_before = session.query(User).filter_by(user_id=user_id).one()
        old_password_hash = user_before.password_hash
        old_temp_password_hash = user_before.temp_password_hash
        with pytest.raises(RuntimeError, match="audit unavailable"):
            password_reset_module.reset_password_with_temp_password(
                session,
                soeid="session-regression-user",
                temp_password="TempPassword123",
                new_password="ReplacementPassword123",
            )

        persisted_user = session.query(User).filter_by(user_id=user_id).one()
        active = session.query(AuthSession).filter_by(session_id=active_session_id).one()
        assert persisted_user.password_hash == old_password_hash
        assert persisted_user.temp_password_hash == old_temp_password_hash
        assert active.revoked_at is None
