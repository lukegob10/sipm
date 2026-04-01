from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
import secrets

from fastapi import status
from sqlalchemy.orm import Session

from ..auth.auth import (
    ONE_TIME_RESET_TOKEN_EXPIRE_MINUTES,
    hash_password,
    verify_password,
)
from ..models import User
from ..security import security_http_exception
from .audit_log import log_changes

_TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
_MIN_TEMP_PASSWORD_RESET_MINUTES = 5
_MAX_TEMP_PASSWORD_RESET_MINUTES = 24 * 60


def _generate_temp_password(length: int = 14) -> str:
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(max(int(length), 10)))


def issue_temp_password(
    session: Session,
    *,
    target_user: User,
    issued_by_user_id: str,
    expires_minutes: Optional[int] = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    ttl = ONE_TIME_RESET_TOKEN_EXPIRE_MINUTES
    if expires_minutes is not None:
        ttl = int(expires_minutes)
        if ttl < _MIN_TEMP_PASSWORD_RESET_MINUTES or ttl > _MAX_TEMP_PASSWORD_RESET_MINUTES:
            raise ValueError(
                "expires_minutes must be between "
                f"{_MIN_TEMP_PASSWORD_RESET_MINUTES} and {_MAX_TEMP_PASSWORD_RESET_MINUTES}."
            )
    expires_at = now + timedelta(minutes=ttl)
    temp_password = _generate_temp_password()

    # Force a reset path and invalidate any active access token sessions.
    target_user.force_password_reset = True
    target_user.temp_password_hash = hash_password(temp_password)
    target_user.temp_password_expires_at = expires_at
    target_user.failed_attempts = 0
    target_user.locked_until = None
    target_user.password_changed_at = now

    session.add(target_user)
    log_changes(
        session,
        entity_type="user",
        entity_id=target_user.user_id,
        user_id=issued_by_user_id,
        action="password_reset_requested",
    )
    session.commit()
    return temp_password, expires_at


def reset_password_with_temp_password(
    session: Session,
    *,
    soeid: str,
    temp_password: str,
    new_password: str,
) -> User:
    now = datetime.now(timezone.utc)
    soeid_norm = str(soeid or "").strip().lower()
    user = session.query(User).filter(User.soeid == soeid_norm).first()
    if not user or not user.is_active:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_INACTIVE_OR_MISSING",
            message="User inactive or missing",
        )

    if not user.temp_password_hash or not user.temp_password_expires_at:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TEMP_PASSWORD_INVALID",
            message="Temporary password is invalid",
        )

    expires_at = user.temp_password_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TEMP_PASSWORD_EXPIRED",
            message="Temporary password expired",
        )

    if not verify_password(temp_password, user.temp_password_hash):
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TEMP_PASSWORD_INVALID",
            message="Temporary password is invalid",
        )

    user.password_hash = hash_password(new_password)
    user.force_password_reset = False
    user.failed_attempts = 0
    user.locked_until = None
    user.temp_password_hash = None
    user.temp_password_expires_at = None
    user.password_changed_at = now

    session.add(user)
    log_changes(
        session,
        entity_type="user",
        entity_id=user.user_id,
        user_id=user.user_id,
        action="password_reset_complete",
    )
    session.commit()
    session.refresh(user)
    return user
