from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.orm import Session

from ..models import User
from ..security import security_http_exception

DEFAULT_MAX_AUTH_FAILURES = 5
DEFAULT_LOCKOUT_MINUTES = 15


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def user_is_locked(user: User, now: datetime | None = None) -> bool:
    locked_until = user.locked_until
    if not locked_until:
        return False
    locked_until = ensure_aware_utc(locked_until)
    return locked_until > (now or now_utc())


def clear_expired_lockout(user: User, now: datetime | None = None) -> None:
    now = now or now_utc()
    if not user.locked_until or user_is_locked(user, now):
        return
    user.failed_attempts = 0
    user.locked_until = None


def reject_if_locked(
    user: User, *, now: datetime | None = None, message: str = "Account locked"
) -> None:
    now = now or now_utc()
    if user_is_locked(user, now):
        raise security_http_exception(
            status_code=status.HTTP_423_LOCKED,
            code="ACCOUNT_LOCKED",
            message=message,
        )
    clear_expired_lockout(user, now)


def record_auth_failure(
    session: Session,
    user: User,
    *,
    now: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_AUTH_FAILURES,
    lockout_minutes: int = DEFAULT_LOCKOUT_MINUTES,
) -> None:
    now = now or now_utc()
    user.failed_attempts += 1
    if user.failed_attempts >= max_attempts:
        user.locked_until = now + timedelta(minutes=lockout_minutes)
    session.add(user)
    session.commit()
