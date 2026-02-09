from datetime import datetime, timedelta, timezone
from typing import Optional
import os
import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from ..auth.auth import (
    clear_auth_cookies,
    create_token,
    decode_token,
    hash_password,
    set_active_space_cookie,
    set_reset_cookie,
    clear_reset_cookie,
    set_auth_cookies,
    verify_password,
)
from ..deps import get_db, require_user
from ..models import User
from ..schemas import (
    ActiveSpaceResponse,
    ActiveSpaceSwitchRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
    UserRead,
    VerifyTempPasswordRequest,
)
from ..services.audit_log import log_changes
from ..services.spaces import resolve_active_space_context

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
TEMP_PASSWORD_EXPIRE_MINUTES = 60


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
    soeid_norm = str(payload.soeid).strip().lower()
    if not soeid_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SOEID is required")
    existing = _get_user_by_soeid(session, soeid_norm)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SOEID already registered")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login failed. Check your username or password.")

    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Login failed. Check your username or password.")

    if _is_user_locked(user, now):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account locked. Try again later.")

    if user.force_password_reset:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password reset required")

    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
        session.add(user)
        session.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Login failed. Check your username or password.")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_token(token, expected_type="refresh")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")
    if _is_user_locked(user, datetime.now(timezone.utc)):
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="Account locked")

    access_token = create_token(user.user_id, user.role, "access")
    refresh_token = create_token(user.user_id, user.role, "refresh")
    set_auth_cookies(response, access_token, refresh_token)
    requested_space_id = request.headers.get("X-Space-Id") or request.cookies.get("active_space_id")
    active_ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    set_active_space_cookie(response, active_ctx.space_id)
    return user


@router.post("/admin-reset")
def admin_reset(payload: ForgotPasswordRequest, session: Session = Depends(get_db)):
    identifier = _normalize_identifier(payload.identifier)
    soeid = _soeid_from_identifier(identifier)
    user = _get_user_by_soeid(session, soeid)
    if not user:
        return {"status": "ok", "temp_password": None}

    temp_password = secrets.token_urlsafe(12)
    now = datetime.now(timezone.utc)
    user.temp_password_hash = hash_password(temp_password)
    user.temp_password_expires_at = now + timedelta(minutes=TEMP_PASSWORD_EXPIRE_MINUTES)
    user.force_password_reset = True
    session.add(user)
    session.commit()

    log_changes(
        session,
        entity_type="user",
        entity_id=user.user_id,
        user_id=user.user_id,
        action="password_reset_admin",
    )
    session.commit()

    return {"status": "ok", "temp_password": temp_password}


@router.post("/verify-temp-password")
def verify_temp_password(
    payload: VerifyTempPasswordRequest,
    response: Response,
    session: Session = Depends(get_db),
):
    soeid_norm = str(payload.soeid).strip().lower()
    user = _get_user_by_soeid(session, soeid_norm)
    if not user or not user.is_active or not user.temp_password_hash or not user.temp_password_expires_at:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    now = datetime.now(timezone.utc)
    expires_at = user.temp_password_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Temporary password expired")

    if not verify_password(payload.temp_password, user.temp_password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.force_password_reset = True
    user.temp_password_hash = None
    user.temp_password_expires_at = None
    user.failed_attempts = 0
    user.locked_until = None
    session.add(user)
    session.commit()

    reset_token = create_token(user.user_id, user.role, "reset")
    set_reset_cookie(response, reset_token)
    return {"status": "ok"}


@router.post("/reset-password")
def reset_password(
    payload: ResetPasswordRequest,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
):
    token = request.cookies.get("reset_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    reset_payload = decode_token(token, expected_type="reset")
    user_id = reset_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User inactive or missing")

    if not user.force_password_reset:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password reset not required")

    if not payload.new_password or payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    now = datetime.now(timezone.utc)
    user.password_hash = hash_password(payload.new_password)
    user.force_password_reset = False
    user.failed_attempts = 0
    user.locked_until = None
    user.password_changed_at = now
    session.add(user)
    session.commit()

    log_changes(
        session,
        entity_type="user",
        entity_id=user.user_id,
        user_id=user.user_id,
        action="password_reset_complete",
    )
    session.commit()

    clear_auth_cookies(response)
    clear_reset_cookie(response)
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Space is not accessible")
    set_active_space_cookie(response, ctx.space_id)
    return ActiveSpaceResponse(
        space_id=ctx.space_id,
        space_name=ctx.space_name,
        space_role=ctx.space_role,
        is_global_admin=ctx.is_global_admin,
    )
