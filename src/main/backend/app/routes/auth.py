from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ..auth.auth import (
    ALLOW_SELF_REGISTER,
    clear_auth_cookies,
    create_token,
    decode_token,
    hash_password,
    set_active_space_cookie,
    set_auth_cookies,
    verify_password,
)
from ..deps import get_db, require_global_admin, require_user
from ..models import User
from ..schemas import (
    ActiveSpaceResponse,
    ActiveSpaceSwitchRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ResetPasswordWithTokenRequest,
    UserCreate,
    UserLogin,
    UserRead,
)
from ..security import security_http_exception
from ..services.password_reset import consume_reset_token
from ..services.spaces import resolve_active_space_context

router = APIRouter()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _get_user_by_soeid(session: Session, soeid: str) -> Optional[User]:
    return session.query(User).filter(User.soeid == soeid.lower()).first()


def _is_user_locked(user: User, now: datetime) -> bool:
    locked_until = user.locked_until
    if not locked_until:
        return False
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > now


def _normalize_identifier(identifier: str) -> str:
    return identifier.strip().lower()


def _soeid_from_identifier(identifier: str) -> str:
    ident = _normalize_identifier(identifier)
    if "@" in ident:
        return ident.split("@", 1)[0]
    return ident


def _email_from_soeid(soeid: str) -> str:
    domain = os.getenv("DOMAIN_NAME", "citi.com")
    return f"{soeid}@{domain}"


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, session: Session = Depends(get_db)):
    if not ALLOW_SELF_REGISTER:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="SELF_REGISTRATION_DISABLED",
            message="Self-registration is disabled",
        )

    soeid_norm = str(payload.soeid).strip().lower()
    if not soeid_norm:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_INPUT",
            message="SOEID is required",
        )
    existing = _get_user_by_soeid(session, soeid_norm)
    if existing:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="DUPLICATE_SOEID",
            message="SOEID already registered",
        )

    now = datetime.now(timezone.utc)
    user = User(
        soeid=soeid_norm,
        email=_email_from_soeid(soeid_norm),
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        role="user",
        is_active=True,
        password_changed_at=now,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token = create_token(user.user_id, user.role, "access")
    refresh_token = create_token(user.user_id, user.role, "refresh")
    set_auth_cookies(response, access_token, refresh_token)
    active_ctx = resolve_active_space_context(session, user, requested_space_id=None)
    set_active_space_cookie(response, active_ctx.space_id)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: UserLogin, request: Request, response: Response, session: Session = Depends(get_db)):
    soeid_norm = str(payload.soeid).strip().lower()
    user = _get_user_by_soeid(session, soeid_norm)
    now = datetime.now(timezone.utc)
    if not user:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="LOGIN_FAILED",
            message="Login failed. Check your username or password.",
        )

    if not user.is_active:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="USER_INACTIVE",
            message="Login failed. Check your username or password.",
        )

    if _is_user_locked(user, now):
        raise security_http_exception(
            status_code=status.HTTP_423_LOCKED,
            code="ACCOUNT_LOCKED",
            message="Account locked. Try again later.",
        )

    if user.force_password_reset:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PASSWORD_RESET_REQUIRED",
            message="Password reset required",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
        session.add(user)
        session.commit()
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="LOGIN_FAILED",
            message="Login failed. Check your username or password.",
        )

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    session.add(user)
    session.commit()
    session.refresh(user)

    access_token = create_token(user.user_id, user.role, "access")
    refresh_token = create_token(user.user_id, user.role, "refresh")
    set_auth_cookies(response, access_token, refresh_token)
    requested_space_id = request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")
    active_ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    set_active_space_cookie(response, active_ctx.space_id)
    return user


@router.post("/refresh", response_model=UserRead)
def refresh(request: Request, response: Response, session: Session = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="AUTH_REQUIRED",
            message="Not authenticated",
        )
    payload = decode_token(token, expected_type="refresh")
    user_id = payload.get("sub")
    if not user_id:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="TOKEN_SUBJECT_INVALID",
            message="Invalid token",
        )
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_active:
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="USER_INACTIVE_OR_MISSING",
            message="User inactive or missing",
        )
    if user.force_password_reset:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PASSWORD_RESET_REQUIRED",
            message="Password reset required",
        )
    if _is_user_locked(user, datetime.now(timezone.utc)):
        raise security_http_exception(
            status_code=status.HTTP_423_LOCKED,
            code="ACCOUNT_LOCKED",
            message="Account locked",
        )

    access_token = create_token(user.user_id, user.role, "access")
    refresh_token = create_token(user.user_id, user.role, "refresh")
    set_auth_cookies(response, access_token, refresh_token)
    requested_space_id = request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")
    active_ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    set_active_space_cookie(response, active_ctx.space_id)
    return user


@router.post("/admin-reset")
def admin_reset_removed(
    payload: ForgotPasswordRequest,
    _admin: User = Depends(require_global_admin),
):
    _ = payload
    raise security_http_exception(
        status_code=status.HTTP_410_GONE,
        code="ENDPOINT_REMOVED",
        message="Use /api/users/{user_id}/password-reset-request",
    )


@router.post("/verify-temp-password")
def verify_temp_password_removed():
    raise security_http_exception(
        status_code=status.HTTP_410_GONE,
        code="ENDPOINT_REMOVED",
        message="Use /api/auth/reset-password-with-token",
    )


@router.post("/reset-password")
def reset_password_removed(payload: ResetPasswordRequest):
    _ = payload
    raise security_http_exception(
        status_code=status.HTTP_410_GONE,
        code="ENDPOINT_REMOVED",
        message="Use /api/auth/reset-password-with-token",
    )


@router.post("/reset-password-with-token")
def reset_password_with_token(
    payload: ResetPasswordWithTokenRequest,
    response: Response,
    session: Session = Depends(get_db),
):
    if not payload.new_password or payload.new_password != payload.confirm_password:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="RESET_PASSWORD_MISMATCH",
            message="Passwords do not match",
        )

    consume_reset_token(session, token=payload.reset_token, new_password=payload.new_password)
    clear_auth_cookies(response)
    return {"status": "ok"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response):
    clear_auth_cookies(response)
    return None


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(require_user)):
    return current_user


@router.get("/active-space", response_model=ActiveSpaceResponse)
def get_active_space(
    request: Request,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    requested_space_id = request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")
    ctx = resolve_active_space_context(session, current_user, requested_space_id=requested_space_id)
    return ActiveSpaceResponse(
        space_id=ctx.space_id,
        space_name=ctx.space_name,
        space_role=ctx.space_role,
        is_global_admin=ctx.is_global_admin,
    )


@router.post("/active-space", response_model=ActiveSpaceResponse)
def switch_active_space(
    payload: ActiveSpaceSwitchRequest,
    response: Response,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    ctx = resolve_active_space_context(session, current_user, requested_space_id=payload.space_id)
    if ctx.space_id != payload.space_id:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="FORBIDDEN_SPACE",
            message="Space is not accessible",
        )
    set_active_space_cookie(response, ctx.space_id)
    return ActiveSpaceResponse(
        space_id=ctx.space_id,
        space_name=ctx.space_name,
        space_role=ctx.space_role,
        is_global_admin=ctx.is_global_admin,
    )
