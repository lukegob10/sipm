from __future__ import annotations

"""
Shared FastAPI dependencies.

This module is intentionally the canonical import target for `get_db` so tests can
override it via `fastapi_app.dependency_overrides[deps.get_db] = ...`.
"""

from datetime import datetime, timedelta, timezone
from typing import Iterator

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .auth.auth import decode_token
from .db.db import get_session
from .models import User
from .services.spaces import SpaceContext, resolve_active_space_context


def get_db() -> Iterator[Session]:
    # Keep indirection so tests can monkeypatch `get_session` on this module.
    yield from get_session()


def require_user(request: Request, session: Session = Depends(get_db)) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    token_issued_at = payload.get("iat")
    if token_issued_at and user.password_changed_at:
        issued_at = datetime.fromtimestamp(token_issued_at, tz=timezone.utc)
        changed_at = user.password_changed_at
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=timezone.utc)
        # Allow 1s clock/precision skew between token iat (seconds) and DB timestamp (microseconds).
        if issued_at < (changed_at - timedelta(seconds=1)):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token no longer valid")
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account locked")
    request.state.user = user
    return user


def current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def current_space(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SpaceContext:
    requested_space_id = request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")
    ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    request.state.space_context = ctx
    return ctx


def require_global_admin(user: User = Depends(require_user)) -> User:
    if (user.role or "").strip().lower() != "global_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global admin required")
    return user


_SPACE_ROLE_ORDER = {"member": 1, "space_admin": 2}


def _normalize_space_role(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized


def require_space_role(min_role: str):
    min_norm = _normalize_space_role(min_role)
    threshold = _SPACE_ROLE_ORDER.get(min_norm)
    if threshold is None:
        raise ValueError(f"Unknown min_role '{min_role}'")

    def _dep(ctx: SpaceContext = Depends(current_space)) -> SpaceContext:
        if ctx.is_global_admin:
            return ctx
        current_rank = _SPACE_ROLE_ORDER.get(_normalize_space_role(ctx.space_role), 0)
        if current_rank < threshold:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient space role")
        return ctx

    return _dep


__all__ = [
    "get_db",
    "get_session",
    "require_user",
    "current_user",
    "current_space",
    "require_space_role",
    "require_global_admin",
]
