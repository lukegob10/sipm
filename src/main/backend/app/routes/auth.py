from datetime import datetime, timedelta, timezone
from typing import Optional
import os

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from ..auth.auth import (
    ACTIVE_SPACE_COOKIE,
    SESSION_ACTIVITY_HEARTBEAT_SECONDS,
    SESSION_IDLE_MINUTES,
    SESSION_IDLE_WARNING_SECONDS,
    allow_self_register,
    clear_auth_cookies,
    create_token,
    decode_token,
    hash_password,
    set_active_space_cookie,
    set_auth_cookies,
    verify_password,
)
from ..deps import ensure_token_not_revoked, get_db, require_global_admin, require_user
from ..models import AuthSession, User
from ..paths import API_PREFIX
from ..schemas import (
    ActiveSpaceResponse,
    ActiveSpaceSwitchRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    SessionActivityRead,
    SessionPolicyRead,
    UserCreate,
    UserLogin,
    UserRead,
)
from ..security import security_http_exception
from ..services.password_reset import reset_password_with_temp_password
from ..services.auth_sessions import (
    create_auth_session,
    record_activity,
    require_auth_session,
    revoke_auth_session,
)
from ..services.spaces import ensure_space_membership, get_or_create_default_space, resolve_active_space_context
from ..services.usage_analytics import usage_analytics_enabled

router = APIRouter()

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
_DUMMY_LOGIN_PASSWORD_HASH = hash_password("not-the-real-password")


def _get_user_by_soeid(session: Session, soeid: str) -> Optional[User]:
    return session.query(User).filter(User.soeid == soeid.lower()).first()


def _is_user_locked(user: User, now: datetime) -> bool:
    locked_until = user.locked_until
    if not locked_until:
        return False
    if locked_until.tzinfo is None:
        locked_until = locked_until.replace(tzinfo=timezone.utc)
    return locked_until > now


def _clear_expired_lockout(user: User, now: datetime) -> None:
    if not user.locked_until or _is_user_locked(user, now):
        return
    user.failed_attempts = 0
    user.locked_until = None


def _email_from_soeid(soeid: str) -> str:
    domain = os.getenv("DOMAIN_NAME", "citi.com")
    return f"{soeid}@{domain}"


def _requested_space_id(request: Request) -> str | None:
    return request.headers.get("X-Space-Id") or request.cookies.get(ACTIVE_SPACE_COOKIE)


def _issue_session(response: Response, session: Session, user: User, requested_space_id: str | None) -> None:
    auth_session = create_auth_session(session, user)
    access_token = create_token(user.user_id, user.role, "access", session_id=auth_session.session_id)
    refresh_token = create_token(user.user_id, user.role, "refresh", session_id=auth_session.session_id)
    set_auth_cookies(response, access_token, refresh_token)
    active_ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    set_active_space_cookie(response, active_ctx.space_id)
    session.commit()


def _provision_self_registered_space(session: Session, user: User) -> None:
    default_space = get_or_create_default_space(session)
    ensure_space_membership(session, user, default_space.space_id, role="member")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, response: Response, session: Session = Depends(get_db)):
    if not allow_self_register():
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

    _provision_self_registered_space(session, user)
    _issue_session(response, session, user, requested_space_id=None)
    return user


@router.post("/login", response_model=UserRead)
def login(payload: UserLogin, request: Request, response: Response, session: Session = Depends(get_db)):
    soeid_norm = str(payload.soeid).strip().lower()
    user = _get_user_by_soeid(session, soeid_norm)
    now = datetime.now(timezone.utc)
    if not user:
        verify_password(payload.password, _DUMMY_LOGIN_PASSWORD_HASH)
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="LOGIN_FAILED",
            message="Login failed. Check your username or password.",
        )

    if not user.is_active:
        verify_password(payload.password, user.password_hash)
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

    _clear_expired_lockout(user, now)

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

    if user.force_password_reset:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="PASSWORD_RESET_REQUIRED",
            message="Password reset required",
        )

    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = now
    session.add(user)
    session.commit()
    session.refresh(user)

    _issue_session(response, session, user, requested_space_id=_requested_space_id(request))
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
    ensure_token_not_revoked(user, payload.get("iat"))
    auth_session = require_auth_session(session, payload, user_id=user.user_id)
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

    access_token = create_token(user.user_id, user.role, "access", session_id=auth_session.session_id)
    refresh_token = create_token(user.user_id, user.role, "refresh", session_id=auth_session.session_id)
    set_auth_cookies(response, access_token, refresh_token)
    active_ctx = resolve_active_space_context(session, user, requested_space_id=_requested_space_id(request))
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
        message=f"Use {API_PREFIX}/users/{{user_id}}/password-reset-request",
    )


@router.post("/verify-temp-password")
def verify_temp_password_removed():
    raise security_http_exception(
        status_code=status.HTTP_410_GONE,
        code="ENDPOINT_REMOVED",
        message=f"Use {API_PREFIX}/auth/reset-password",
    )


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    response: Response,
    session: Session = Depends(get_db),
):
    if not payload.new_password or payload.new_password != payload.confirm_password:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="RESET_PASSWORD_MISMATCH",
            message="Passwords do not match",
        )
    if not payload.soeid or not payload.temp_password:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="RESET_PASSWORD_INPUT_INVALID",
            message="SOEID and temporary password are required",
        )

    reset_password_with_temp_password(
        session,
        soeid=payload.soeid,
        temp_password=payload.temp_password,
        new_password=payload.new_password,
    )
    clear_auth_cookies(response)
    return {"status": "ok"}


@router.post("/reset-password-with-token")
def reset_password_with_token_removed():
    raise security_http_exception(
        status_code=status.HTTP_410_GONE,
        code="ENDPOINT_REMOVED",
        message=f"Use {API_PREFIX}/auth/reset-password",
    )


@router.get("/session-policy", response_model=SessionPolicyRead)
def session_policy():
    return SessionPolicyRead(
        idle_timeout_seconds=SESSION_IDLE_MINUTES * 60,
        warning_seconds=SESSION_IDLE_WARNING_SECONDS,
        activity_heartbeat_seconds=SESSION_ACTIVITY_HEARTBEAT_SECONDS,
    )


@router.post("/activity", response_model=SessionActivityRead)
def activity(
    request: Request,
    session: Session = Depends(get_db),
    _current_user: User = Depends(require_user),
):
    auth_session = getattr(request.state, "auth_session", None)
    if not isinstance(auth_session, AuthSession):
        raise security_http_exception(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="SESSION_REQUIRED",
            message="Interactive session required",
        )
    return SessionActivityRead(idle_expires_at=record_activity(session, auth_session))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, session: Session = Depends(get_db)):
    for cookie_name, token_type in (("access_token", "access"), ("refresh_token", "refresh")):
        token = request.cookies.get(cookie_name)
        if not token:
            continue
        try:
            payload = decode_token(token, expected_type=token_type)
        except Exception:
            continue
        session_id = str(payload.get("sid") or "").strip()
        user_id = str(payload.get("sub") or "").strip()
        if not session_id or not user_id:
            continue
        auth_session = (
            session.query(AuthSession)
            .filter(AuthSession.session_id == session_id, AuthSession.user_id == user_id)
            .first()
        )
        if auth_session:
            revoke_auth_session(session, auth_session)
        break
    clear_auth_cookies(response)
    return None


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(require_user)):
    return user


@router.get("/active-space", response_model=ActiveSpaceResponse)
def get_active_space(
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
):
    requested_space_id = _requested_space_id(request)
    ctx = resolve_active_space_context(session, current_user, requested_space_id=requested_space_id)
    cookie_space_id = request.cookies.get(ACTIVE_SPACE_COOKIE)
    if cookie_space_id != ctx.space_id:
        set_active_space_cookie(response, ctx.space_id)
    return ActiveSpaceResponse(
        space_id=ctx.space_id,
        space_name=ctx.space_name,
        space_role=ctx.space_role,
        is_global_admin=ctx.is_global_admin,
        space_kind=ctx.space_kind,
        owner_user_id=ctx.owner_user_id,
        usage_analytics_enabled=usage_analytics_enabled(),
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
        space_kind=ctx.space_kind,
        owner_user_id=ctx.owner_user_id,
        usage_analytics_enabled=usage_analytics_enabled(),
    )
