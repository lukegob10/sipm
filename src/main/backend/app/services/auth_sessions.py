from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import hmac

from sqlalchemy.orm import Session

from ..auth.auth import SESSION_IDLE_MINUTES
from ..models import AuthSession, User
from ..security import security_http_exception


SESSION_BINDING_HEADER = "X-SIPM-Session"


def session_binding(session_id: str) -> str:
    """Return a non-credential fingerprint identifying an interactive session."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def require_session_binding(expected: str | None, session_id: str) -> None:
    # Omitted headers preserve compatibility for non-browser and older clients.
    if expected is None:
        return
    actual = session_binding(session_id)
    if not session_id or not expected.isascii() or not hmac.compare_digest(expected, actual):
        raise security_http_exception(
            status_code=409,
            code="SESSION_CONTEXT_CHANGED",
            message="Your session changed in another tab.",
        )


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def idle_deadline(auth_session: AuthSession) -> datetime:
    return auth_session.last_activity_at + timedelta(minutes=SESSION_IDLE_MINUTES)


def create_auth_session(session: Session, user: User) -> AuthSession:
    auth_session = AuthSession(user_id=user.user_id, last_activity_at=utcnow_naive())
    session.add(auth_session)
    session.flush()
    return auth_session


def require_auth_session(session: Session, payload: dict, *, user_id: str) -> AuthSession:
    session_id = str(payload.get("sid") or "").strip()
    if not session_id:
        raise security_http_exception(
            status_code=401,
            code="SESSION_REQUIRED",
            message="Session sign-in required",
        )
    auth_session = (
        session.query(AuthSession)
        .filter(AuthSession.session_id == session_id, AuthSession.user_id == user_id)
        .first()
    )
    if not auth_session:
        raise security_http_exception(
            status_code=401,
            code="SESSION_REVOKED",
            message="Session no longer valid",
        )
    if auth_session.revoked_at is not None:
        raise security_http_exception(
            status_code=401,
            code="SESSION_REVOKED",
            message="Session no longer valid",
        )
    if idle_deadline(auth_session) <= utcnow_naive():
        raise security_http_exception(
            status_code=401,
            code="SESSION_IDLE_EXPIRED",
            message="Session expired due to inactivity",
        )
    return auth_session


def record_activity(session: Session, auth_session: AuthSession) -> datetime:
    now = utcnow_naive()
    cutoff = now - timedelta(minutes=SESSION_IDLE_MINUTES)
    updated = (
        session.query(AuthSession)
        .filter(
            AuthSession.session_id == auth_session.session_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.last_activity_at > cutoff,
            AuthSession.last_activity_at <= now,
        )
        .update({AuthSession.last_activity_at: now}, synchronize_session=False)
    )
    if updated != 1:
        session.rollback()
        current_session = require_auth_session(
            session,
            {"sid": auth_session.session_id},
            user_id=auth_session.user_id,
        )
        deadline = idle_deadline(current_session)
        session.commit()
        return deadline
    session.commit()
    return now + timedelta(minutes=SESSION_IDLE_MINUTES)


def revoke_user_auth_sessions(
    session: Session,
    *,
    user_id: str,
    revoked_at: datetime | None = None,
) -> int:
    """Revoke all active interactive sessions without committing the transaction."""
    timestamp = revoked_at or utcnow_naive()
    return (
        session.query(AuthSession)
        .filter(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .update({AuthSession.revoked_at: timestamp}, synchronize_session=False)
    )


def revoke_auth_session(session: Session, auth_session: AuthSession) -> None:
    if auth_session.revoked_at is None:
        auth_session.revoked_at = utcnow_naive()
        session.add(auth_session)
        session.commit()
