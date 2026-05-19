from __future__ import annotations

"""
Shared FastAPI dependencies.

This module is intentionally the canonical import target for `get_db` so tests can
override it via `fastapi_app.dependency_overrides[deps.get_db] = ...`.
"""

from datetime import datetime, timedelta, timezone
from typing import Iterator

from fastapi import Depends, Request, status
from sqlalchemy.orm import Session

from .auth.auth import decode_token
from .db.db import get_session
from .models import User
from .security import security_http_exception
from .services.audit_log import log_changes
from .services.api_tokens import authenticate_api_token
from .services.spaces import SpaceContext, is_global_admin_role, resolve_active_space_context


def get_db() -> Iterator[Session]:
    # Keep indirection so tests can monkeypatch `get_session` on this module.
    yield from get_session()


def _audit_permission_denied(
    session: Session,
    *,
    user_id: str,
    space_id: str | None,
    action: str,
    reason: str,
) -> None:
    try:
        log_changes(
            session,
            entity_type="authz",
            entity_id=space_id or "global",
            user_id=user_id,
            action=action,
            changes={"reason": (None, reason)},
            space_id=space_id,
        )
        session.commit()
    except Exception:
        session.rollback()


def _raise_auth_required() -> None:
    raise security_http_exception(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="AUTH_REQUIRED",
        message="Not authenticated",
    )


def _raise_forbidden_space() -> None:
    raise security_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        code="FORBIDDEN_SPACE",
        message="Space is not accessible",
    )


def _raise_forbidden_role(message: str) -> None:
    raise security_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        code="FORBIDDEN_ROLE",
        message=message,
    )


def _ensure_user_not_locked(user: User) -> None:
    if not user.locked_until:
        return
    locked_until = user.locked_until
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    if locked_until > datetime.now(timezone.utc):
        raise security_http_exception(
            status_code=status.HTTP_423_LOCKED,
            code="ACCOUNT_LOCKED",
            message="Account locked",
        )


def authenticate_access_token(session: Session, token: str | None) -> User:
    if not token:
        _raise_auth_required()
    payload = decode_token(token, expected_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_SUBJECT_INVALID",
            message="Invalid token subject",
        )
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_active:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_INACTIVE_OR_MISSING",
            message="User inactive or missing",
        )
    ensure_token_not_revoked(user, payload.get("iat"))
    _ensure_user_not_locked(user)
    return user


def ensure_token_not_revoked(user: User, token_issued_at: int | None) -> None:
    if not token_issued_at or not user.password_changed_at:
        return
    issued_at = datetime.fromtimestamp(token_issued_at, tz=timezone.utc)
    changed_at = user.password_changed_at
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)
    # Allow 1s clock/precision skew between token iat (seconds) and DB timestamp (microseconds).
    if issued_at < (changed_at - timedelta(seconds=1)):
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_REVOKED",
            message="Token no longer valid",
        )


def _bearer_credential(request: Request) -> str | None:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    scheme, _, credential = auth_header.partition(" ")
    if scheme.lower() == "bearer" and credential.strip():
        return credential.strip()
    return None


def _cookie_access_token(request: Request) -> str | None:
    return request.cookies.get("access_token")


def _set_authenticated_user(request: Request, user: User, *, auth_method: str) -> User:
    request.state.auth_method = auth_method
    request.state.user = user
    return user


def require_user(request: Request, session: Session = Depends(get_db)) -> User:
    bearer_token = _bearer_credential(request)
    if bearer_token:
        user = authenticate_api_token(session, bearer_token)
        return _set_authenticated_user(request, user, auth_method="api_token")
    token = _cookie_access_token(request)
    if token:
        user = authenticate_access_token(session, token)
        return _set_authenticated_user(request, user, auth_method="cookie")
    return authenticate_access_token(session, None)


def current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        _raise_auth_required()
    return user


def _requested_space_id(request: Request) -> str | None:
    return request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")


def _ensure_space_matches_request(requested_space_id: str | None, ctx: SpaceContext) -> None:
    if requested_space_id and ctx.space_id != requested_space_id:
        _raise_forbidden_space()


def current_space(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SpaceContext:
    requested_space_id = _requested_space_id(request)
    ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    _ensure_space_matches_request(requested_space_id, ctx)
    request.state.space_context = ctx
    return ctx


def require_global_admin(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> User:
    if not is_global_admin_role(user.role):
        _audit_permission_denied(
            session,
            user_id=user.user_id,
            space_id=None,
            action="forbidden_global_admin",
            reason="Global admin required",
        )
        _raise_forbidden_role("Global admin required")
    return user


_SPACE_ROLE_ORDER = {"member": 1, "space_admin": 2}


def _normalize_space_role(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized


def _resolve_space_role_dependency_args(
    request: Request | SpaceContext,
    ctx: SpaceContext,
) -> tuple[Request | None, SpaceContext]:
    if isinstance(request, SpaceContext):
        return None, request
    if not isinstance(ctx, SpaceContext):
        raise RuntimeError("Space context dependency was not resolved")
    return request, ctx


def require_space_role(min_role: str):
    min_norm = _normalize_space_role(min_role)
    threshold = _SPACE_ROLE_ORDER.get(min_norm)
    if threshold is None:
        raise ValueError(f"Unknown min_role '{min_role}'")

    def _dep(
        request: Request,
        session: Session = Depends(get_db),
        ctx: SpaceContext = Depends(current_space),
    ) -> SpaceContext:
        request, ctx = _resolve_space_role_dependency_args(request, ctx)
        if ctx.is_global_admin:
            return ctx
        current_rank = _SPACE_ROLE_ORDER.get(_normalize_space_role(ctx.space_role), 0)
        if current_rank < threshold:
            user = getattr(getattr(request, "state", None), "user", None)
            if user and getattr(user, "user_id", None) and hasattr(session, "commit"):
                _audit_permission_denied(
                    session,
                    user_id=user.user_id,
                    space_id=ctx.space_id,
                    action="forbidden_space_role",
                    reason=f"Insufficient space role for '{min_norm}'",
                )
            _raise_forbidden_role("Insufficient space role")
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
    "authenticate_access_token",
    "ensure_token_not_revoked",
]
