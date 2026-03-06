from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import status
from sqlalchemy.orm import Session

from ..auth.auth import (
    ONE_TIME_RESET_TOKEN_EXPIRE_MINUTES,
    generate_one_time_reset_token,
    hash_one_time_reset_token,
    hash_password,
)
from ..models import PasswordResetToken, User
from ..security import security_http_exception
from .audit_log import log_changes


def issue_reset_token(
    session: Session,
    *,
    target_user: User,
    issued_by_user_id: str,
    expires_minutes: Optional[int] = None,
) -> tuple[str, datetime]:
    now = datetime.now(timezone.utc)
    ttl = ONE_TIME_RESET_TOKEN_EXPIRE_MINUTES
    if expires_minutes is not None:
        ttl = max(5, min(int(expires_minutes), 24 * 60))
    expires_at = now + timedelta(minutes=ttl)

    # Invalidate prior unused tokens for this user.
    active_rows = (
        session.query(PasswordResetToken)
        .filter(PasswordResetToken.user_id == target_user.user_id)
        .filter(PasswordResetToken.used_at.is_(None))
        .all()
    )
    for row in active_rows:
        row.used_at = now
        row.updated_at = now
        session.add(row)

    reset_token = generate_one_time_reset_token()
    token_row = PasswordResetToken(
        reset_token_id=str(uuid4()),
        user_id=target_user.user_id,
        issued_by_user_id=issued_by_user_id,
        token_hash=hash_one_time_reset_token(reset_token),
        expires_at=expires_at,
        used_at=None,
        created_at=now,
        updated_at=now,
    )

    # Force reset and invalidate any active access token sessions.
    target_user.force_password_reset = True
    target_user.temp_password_hash = None
    target_user.temp_password_expires_at = None
    target_user.failed_attempts = 0
    target_user.locked_until = None
    target_user.password_changed_at = now

    session.add(target_user)
    session.add(token_row)
    log_changes(
        session,
        entity_type="user",
        entity_id=target_user.user_id,
        user_id=issued_by_user_id,
        action="password_reset_requested",
    )
    session.commit()
    return reset_token, expires_at


def consume_reset_token(
    session: Session,
    *,
    token: str,
    new_password: str,
) -> User:
    now = datetime.now(timezone.utc)
    token_hash = hash_one_time_reset_token(token)
    row = (
        session.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )
    if not row:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="RESET_TOKEN_INVALID",
            message="Reset token is invalid",
        )
    if row.used_at is not None:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="RESET_TOKEN_USED",
            message="Reset token has already been used",
        )

    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="RESET_TOKEN_EXPIRED",
            message="Reset token expired",
        )

    user = session.query(User).filter(User.user_id == row.user_id).first()
    if not user or not user.is_active:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_INACTIVE_OR_MISSING",
            message="User inactive or missing",
        )

    user.password_hash = hash_password(new_password)
    user.force_password_reset = False
    user.failed_attempts = 0
    user.locked_until = None
    user.temp_password_hash = None
    user.temp_password_expires_at = None
    user.password_changed_at = now

    row.used_at = now
    row.updated_at = now
    session.add(user)
    session.add(row)
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
