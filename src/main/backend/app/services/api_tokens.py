from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import status
from sqlalchemy.orm import Session

from ..models import ApiToken, User
from ..security import security_http_exception

TOKEN_PREFIX = "sipm_pat_"
LAST_USED_WRITE_INTERVAL = timedelta(minutes=5)
API_TOKEN_INVALID_MESSAGE = "Invalid API token"


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def generate_api_token() -> str:
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def api_token_is_active(token: ApiToken, *, now: datetime | None = None) -> bool:
    now = now or _utc_now_naive()
    if token.revoked_at is not None:
        return False
    if token.expires_at is not None and token.expires_at <= now:
        return False
    return True


def authenticate_api_token(session: Session, token: str | None) -> User:
    raw = str(token or "").strip()
    if not raw:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="Not authenticated",
        )
    if not raw.startswith(TOKEN_PREFIX):
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="API_TOKEN_INVALID",
            message=API_TOKEN_INVALID_MESSAGE,
        )
    token_row = session.query(ApiToken).filter(ApiToken.token_hash == hash_api_token(raw)).first()
    if not token_row or not api_token_is_active(token_row):
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="API_TOKEN_INVALID",
            message=API_TOKEN_INVALID_MESSAGE,
        )
    user = session.query(User).filter(User.user_id == token_row.user_id).first()
    if not user or not user.is_active or not user.is_service_account:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="API_TOKEN_INVALID",
            message=API_TOKEN_INVALID_MESSAGE,
        )
    now = _utc_now_naive()
    if token_row.last_used_at is None or token_row.last_used_at <= now - LAST_USED_WRITE_INTERVAL:
        token_row.last_used_at = now
        session.add(token_row)
        session.commit()
    return user


def create_api_token(
    session: Session,
    *,
    target_user: User,
    created_by_user_id: str,
    name: str,
    expires_at: datetime | None = None,
) -> tuple[ApiToken, str]:
    if not target_user.is_service_account:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="SERVICE_ACCOUNT_REQUIRED",
            message="API tokens can only be issued for service accounts",
        )
    raw_token = generate_api_token()
    token = ApiToken(
        user_id=target_user.user_id,
        name=str(name or "").strip(),
        token_hash=hash_api_token(raw_token),
        created_by_user_id=created_by_user_id,
        expires_at=expires_at,
    )
    session.add(token)
    session.commit()
    session.refresh(token)
    return token, raw_token
