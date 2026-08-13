from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import and_, case, or_, update
from sqlalchemy.orm import Session

from ..models import User


def is_user_locked(user: User, now: datetime) -> bool:
    locked_until = user.locked_until
    if not locked_until:
        return False
    if locked_until.tzinfo is None and now.tzinfo is not None:
        locked_until = locked_until.replace(tzinfo=now.tzinfo)
    return locked_until > now


def _authentication_is_unlocked(now: datetime):
    return or_(User.locked_until.is_(None), User.locked_until <= now)


def _record_failed_attempt(
    session: Session,
    *,
    user_id: str,
    now: datetime,
    max_failed_attempts: int,
    lockout_minutes: int,
    eligibility_filters: tuple,
) -> bool:
    expired_lockout = and_(
        User.locked_until.is_not(None),
        User.locked_until <= now,
    )
    threshold_reached = and_(
        User.locked_until.is_(None),
        User.failed_attempts >= max_failed_attempts - 1,
    )
    result = session.execute(
        update(User)
        .where(
            User.user_id == user_id,
            User.is_active,
            _authentication_is_unlocked(now),
            *eligibility_filters,
        )
        .values(
            failed_attempts=case(
                (expired_lockout, 1),
                else_=User.failed_attempts + 1,
            ),
            locked_until=case(
                (
                    threshold_reached,
                    now + timedelta(minutes=lockout_minutes),
                ),
                else_=None,
            ),
        ),
        execution_options={"synchronize_session": False},
    )
    return result.rowcount == 1


def record_failed_login_attempt(
    session: Session,
    *,
    user: User,
    password_hash: str,
    now: datetime,
    max_failed_attempts: int,
    lockout_minutes: int,
) -> bool:
    return _record_failed_attempt(
        session,
        user_id=user.user_id,
        now=now,
        max_failed_attempts=max_failed_attempts,
        lockout_minutes=lockout_minutes,
        eligibility_filters=(User.password_hash == password_hash,),
    )


def record_failed_temp_password_attempt(
    session: Session,
    *,
    user: User,
    temp_password_hash: str,
    now: datetime,
    max_failed_attempts: int,
    lockout_minutes: int,
) -> bool:
    return _record_failed_attempt(
        session,
        user_id=user.user_id,
        now=now,
        max_failed_attempts=max_failed_attempts,
        lockout_minutes=lockout_minutes,
        eligibility_filters=(
            User.temp_password_hash == temp_password_hash,
            User.temp_password_expires_at.is_not(None),
            User.temp_password_expires_at >= now,
        ),
    )


def try_record_successful_login(
    session: Session,
    *,
    user: User,
    password_hash: str,
    now: datetime,
) -> bool:
    result = session.execute(
        update(User)
        .where(
            User.user_id == user.user_id,
            User.password_hash == password_hash,
            User.is_active == True,  # noqa: E712
            User.force_password_reset == False,  # noqa: E712
            _authentication_is_unlocked(now),
        )
        .values(
            failed_attempts=0,
            locked_until=None,
            last_login_at=now,
        ),
        execution_options={"synchronize_session": "evaluate"},
    )
    return result.rowcount == 1


def try_complete_temp_password_reset(
    session: Session,
    *,
    user: User,
    temp_password_hash: str,
    new_password_hash: str,
    now: datetime,
) -> bool:
    result = session.execute(
        update(User)
        .where(
            User.user_id == user.user_id,
            User.temp_password_hash == temp_password_hash,
            User.temp_password_expires_at.is_not(None),
            User.temp_password_expires_at >= now,
            User.is_active,
            _authentication_is_unlocked(now),
        )
        .values(
            password_hash=new_password_hash,
            force_password_reset=False,
            failed_attempts=0,
            locked_until=None,
            temp_password_hash=None,
            temp_password_expires_at=None,
            password_changed_at=now,
        ),
        execution_options={"synchronize_session": False},
    )
    return result.rowcount == 1
