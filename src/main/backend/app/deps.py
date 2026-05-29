"""
Shared FastAPI dependencies.

This module is intentionally the canonical import target for `get_db` so tests can
override it via `fastapi_app.dependency_overrides[deps.get_db] = ...`.
"""

from __future__ import annotations

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


def authenticate_access_token(session: Session, token: str | None) -> User:
    if not token:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="Not authenticated",
        )
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
    if user.locked_until:
        locked_until = user.locked_until
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            raise security_http_exception(
                status_code=status.HTTP_423_LOCKED,
                code="ACCOUNT_LOCKED",
                message="Account locked",
            )
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


def require_user(request: Request, session: Session = Depends(get_db)) -> User:
    bearer_token = _bearer_credential(request)
    if bearer_token:
        user = authenticate_api_token(session, bearer_token)
        request.state.auth_method = "api_token"
        request.state.user = user
        return user
    token = request.cookies.get("access_token")
    if token:
        user = authenticate_access_token(session, token)
        request.state.auth_method = "cookie"
        request.state.user = user
        return user
    user = authenticate_access_token(session, None)
    request.state.user = user
    return user


def require_agent_service_account(
    request: Request, session: Session = Depends(get_db)
) -> User:
    bearer_token = _bearer_credential(request)
    if not bearer_token:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="Bearer API token required",
        )
    user = authenticate_api_token(session, bearer_token)
    if not getattr(user, "is_service_account", False):
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SERVICE_ACCOUNT_REQUIRED",
            message="Service account token required",
        )
    request.state.auth_method = "api_token"
    request.state.user = user
    return user


def current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if not user:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="Not authenticated",
        )
    return user


def require_interactive_user(
    request: Request,
    user: User = Depends(require_user),
) -> User:
    if getattr(request.state, "auth_method", None) == "api_token":
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="INTERACTIVE_USER_REQUIRED",
            message="Interactive user approval required",
        )
    return user


def require_non_agent_write(
    request: Request,
    user: User = Depends(require_user),
) -> User:
    if getattr(request.state, "auth_method", None) == "api_token" and getattr(
        user, "is_service_account", False
    ):
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="AGENT_APPROVAL_REQUIRED",
            message="Service-account writes require the agent approval workflow",
        )
    return user


def current_space(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> SpaceContext:
    requested_space_id = request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")
    ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    if requested_space_id and ctx.space_id != requested_space_id:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_SPACE",
            message="Space is not accessible",
        )
    request.state.space_context = ctx
    return ctx


def current_agent_space(
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(require_agent_service_account),
) -> SpaceContext:
    requested_space_id = request.headers.get("X-Space-Id")
    if not requested_space_id:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_SPACE",
            message="Space is not accessible",
        )
    ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    if ctx.space_id != requested_space_id:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_SPACE",
            message="Space is not accessible",
        )
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
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_ROLE",
            message="Global admin required",
        )
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

    def _dep(
        request: Request,
        session: Session = Depends(get_db),
        ctx: SpaceContext = Depends(current_space),
    ) -> SpaceContext:
        if isinstance(request, SpaceContext):
            ctx = request
            request = None  # type: ignore[assignment]
        if not isinstance(ctx, SpaceContext):
            raise RuntimeError("Space context dependency was not resolved")
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
            raise security_http_exception(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN_ROLE",
                message="Insufficient space role",
            )
        return ctx

    return _dep


def require_agent_space_role(min_role: str):
    min_norm = _normalize_space_role(min_role)
    threshold = _SPACE_ROLE_ORDER.get(min_norm)
    if threshold is None:
        raise ValueError(f"Unknown min_role '{min_role}'")

    def _dep(
        request: Request,
        session: Session = Depends(get_db),
        ctx: SpaceContext = Depends(current_agent_space),
    ) -> SpaceContext:
        if isinstance(request, SpaceContext):
            ctx = request
            request = None  # type: ignore[assignment]
        if not isinstance(ctx, SpaceContext):
            raise RuntimeError("Space context dependency was not resolved")
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
            raise security_http_exception(
                status_code=status.HTTP_403_FORBIDDEN,
                code="FORBIDDEN_ROLE",
                message="Insufficient space role",
            )
        return ctx

    return _dep


__all__ = [
    "get_db",
    "get_session",
    "require_user",
    "require_agent_service_account",
    "require_interactive_user",
    "require_non_agent_write",
    "current_user",
    "current_space",
    "current_agent_space",
    "require_space_role",
    "require_agent_space_role",
    "require_global_admin",
    "authenticate_access_token",
    "ensure_token_not_revoked",
]
