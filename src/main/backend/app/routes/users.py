import csv
from datetime import datetime, timezone
from io import StringIO
import os
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth.auth import hash_bootstrap_password
from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_global_admin,
    require_space_role,
)
from ..models import ApiToken, SpaceMembership, User
from ..schemas import (
    ApiTokenCreate,
    ApiTokenIssueResponse,
    ApiTokenRead,
    PasswordResetIssueRequest,
    PasswordResetIssueResponse,
    UserRead,
    UserUpdate,
)
from ..services.audit_log import log_changes
from ..services.api_tokens import api_token_is_active, create_api_token
from ..services.password_reset import issue_temp_password
from ..services.spaces import SpaceContext, is_global_admin_role
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token
from ..services.user_admin_guards import (
    count_active_global_admins as _count_active_global_admins,
    ensure_actor_can_modify_user,
    ensure_user_can_be_deactivated,
    is_global_admin_user as _is_global_admin,
    normalized_global_role_expr as _normalized_global_role_expr,
)
from ..utils import read_csv

router = APIRouter()
_USERS_LIST_TTL_SECONDS = 20
_USERS_EXPORT_TTL_SECONDS = 30
_HOURS_PER_FTE_CAPACITY = 40.0


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _active_space_user_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(User)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
    )


def _user_or_404(session: Session, user_id: str) -> User:
    user = session.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _user_by_soeid_or_404(session: Session, soeid: str) -> User:
    soeid_norm = soeid.strip().lower()
    user = session.query(User).filter(User.soeid == soeid_norm).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _token_or_404(session: Session, user_id: str, token_id: str) -> ApiToken:
    token = (
        session.query(ApiToken)
        .filter(ApiToken.user_id == user_id)
        .filter(ApiToken.token_id == token_id)
        .first()
    )
    if not token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found")
    return token


def _ensure_service_account_target(user: User) -> None:
    if not user.is_service_account:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API tokens can only be issued for service accounts",
        )


def _is_service_account_only_update(payload: UserUpdate) -> bool:
    return (
        payload.is_service_account is not None
        and payload.display_name is None
        and payload.team_tag is None
        and payload.capacity_fte_month is None
        and payload.capacity_hours is None
        and payload.is_active is None
    )


def _invalidate_user_caches_for_user_memberships(session: Session, user_id: str) -> None:
    rows = (
        session.query(SpaceMembership.space_id)
        .filter(SpaceMembership.user_id == user_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .distinct()
        .all()
    )
    for row in rows:
        space_id = row[0] if isinstance(row, tuple) else getattr(row, "space_id", None)
        if space_id:
            invalidate_space(space_id, ["users"])


def _set_global_admin_role(
    session: Session,
    *,
    actor: User,
    target: User,
    make_global_admin: bool,
) -> User:
    if make_global_admin and _is_global_admin(target):
        return target
    if (not make_global_admin) and (not _is_global_admin(target)):
        return target

    if (not make_global_admin) and target.is_active and _count_active_global_admins(session) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one active global_admin is required",
        )

    before = target.role
    target.role = "global_admin" if make_global_admin else "user"
    session.add(target)
    log_changes(
        session,
        entity_type="user",
        entity_id=target.user_id,
        user_id=actor.user_id,
        action="grant_global_admin" if make_global_admin else "revoke_global_admin",
        changes={"role": (before, target.role)},
    )
    session.commit()
    session.refresh(target)
    _invalidate_user_caches_for_user_memberships(session, target.user_id)
    return target


def _ensure_active_membership_for_user(session: Session, user_id: str, space_id: str) -> None:
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == user_id)
        .first()
    )
    if not membership:
        membership = SpaceMembership(space_id=space_id, user_id=user_id, role="member", status="active")
        session.add(membership)
        return

    changed = False
    if membership.deleted_at is not None:
        membership.deleted_at = None
        changed = True
    if membership.status != "active":
        membership.status = "active"
        changed = True
    if not (membership.role or "").strip():
        membership.role = "member"
        changed = True
    if changed:
        session.add(membership)


def _set_user_capacity_fields(
    user: User,
    *,
    capacity_fte_month: Optional[float] = None,
    capacity_hours: Optional[int] = None,
) -> None:
    if capacity_fte_month is not None:
        fte = max(float(capacity_fte_month), 0.0)
        user.capacity_fte_month = round(fte, 3)
        user.capacity_hours = max(int(round(fte * _HOURS_PER_FTE_CAPACITY)), 0)
        return
    if capacity_hours is not None:
        hours = max(int(capacity_hours), 0)
        user.capacity_hours = hours
        user.capacity_fte_month = round(float(hours) / _HOURS_PER_FTE_CAPACITY, 3)


@router.get("/users", response_model=List[UserRead])
def list_users(
    team_tag: Optional[str] = None,
    active_only: bool = True,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[UserRead]:
    team_tag_norm = team_tag.strip() if team_tag else None
    scope_token = make_scope_token("users", space_ctx.space_id)
    params = {
        "team_tag": team_tag_norm,
        "active_only": bool(active_only),
    }

    def _load():
        query = _active_space_user_query(session, space_ctx)
        if active_only:
            query = query.filter(User.is_active == True)
        if team_tag_norm:
            query = query.filter(User.team_tag == team_tag_norm)
        return [UserRead.model_validate(user).model_dump(mode="json") for user in query.order_by(User.display_name.asc()).all()]

    return cached_call(
        endpoint="users:list",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_USERS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/users/global-admins", response_model=List[UserRead])
def list_global_admin_users(
    active_only: bool = True,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> List[UserRead]:
    query = session.query(User).filter(_normalized_global_role_expr() == "global_admin")
    if active_only:
        query = query.filter(User.is_active == True)
    return query.order_by(User.display_name.asc()).all()


@router.post("/users/{user_id}/global-admin", response_model=UserRead)
def grant_global_admin_by_user_id(
    user_id: str,
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> UserRead:
    user = _user_or_404(session, user_id)
    return _set_global_admin_role(
        session,
        actor=admin_user,
        target=user,
        make_global_admin=True,
    )


@router.delete("/users/{user_id}/global-admin", response_model=UserRead)
def revoke_global_admin_by_user_id(
    user_id: str,
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> UserRead:
    user = _user_or_404(session, user_id)
    return _set_global_admin_role(
        session,
        actor=admin_user,
        target=user,
        make_global_admin=False,
    )


@router.post("/users/by-soeid/{soeid}/global-admin", response_model=UserRead)
def grant_global_admin_by_soeid(
    soeid: str,
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> UserRead:
    user = _user_by_soeid_or_404(session, soeid)
    return _set_global_admin_role(
        session,
        actor=admin_user,
        target=user,
        make_global_admin=True,
    )


@router.delete("/users/by-soeid/{soeid}/global-admin", response_model=UserRead)
def revoke_global_admin_by_soeid(
    soeid: str,
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> UserRead:
    user = _user_by_soeid_or_404(session, soeid)
    return _set_global_admin_role(
        session,
        actor=admin_user,
        target=user,
        make_global_admin=False,
    )



@router.post(
    "/users/{user_id}/password-reset-request",
    response_model=PasswordResetIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_user_password_reset(
    user_id: str,
    payload: Optional[PasswordResetIssueRequest] = Body(default=None),
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> PasswordResetIssueResponse:
    user = _user_or_404(session, user_id)
    temp_password, expires_at = issue_temp_password(
        session,
        target_user=user,
        issued_by_user_id=admin_user.user_id,
        expires_minutes=payload.expires_minutes if payload else None,
    )
    _invalidate_user_caches_for_user_memberships(session, user.user_id)
    return PasswordResetIssueResponse(status="issued", temp_password=temp_password, expires_at=expires_at)


@router.post(
    "/users/by-soeid/{soeid}/password-reset-request",
    response_model=PasswordResetIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
def request_user_password_reset_by_soeid(
    soeid: str,
    payload: Optional[PasswordResetIssueRequest] = Body(default=None),
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> PasswordResetIssueResponse:
    user = _user_by_soeid_or_404(session, soeid)
    temp_password, expires_at = issue_temp_password(
        session,
        target_user=user,
        issued_by_user_id=admin_user.user_id,
        expires_minutes=payload.expires_minutes if payload else None,
    )
    _invalidate_user_caches_for_user_memberships(session, user.user_id)
    return PasswordResetIssueResponse(status="issued", temp_password=temp_password, expires_at=expires_at)


@router.get("/users/{user_id}/api-tokens", response_model=List[ApiTokenRead])
def list_user_api_tokens(
    user_id: str,
    active_only: bool = False,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> List[ApiTokenRead]:
    user = _user_or_404(session, user_id)
    _ensure_service_account_target(user)
    query = session.query(ApiToken).filter(ApiToken.user_id == user.user_id)
    if active_only:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        query = query.filter(ApiToken.revoked_at.is_(None)).filter(
            (ApiToken.expires_at.is_(None)) | (ApiToken.expires_at > now)
        )
    return query.order_by(ApiToken.created_at.desc()).all()


@router.post("/users/{user_id}/api-tokens", response_model=ApiTokenIssueResponse, status_code=status.HTTP_201_CREATED)
def issue_user_api_token(
    user_id: str,
    payload: ApiTokenCreate,
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> ApiTokenIssueResponse:
    user = _user_or_404(session, user_id)
    _ensure_service_account_target(user)
    expires_at = payload.expires_at
    if expires_at is not None:
        if expires_at.tzinfo is not None:
            expires_at = expires_at.astimezone(timezone.utc).replace(tzinfo=None)
        if expires_at <= datetime.now(timezone.utc).replace(tzinfo=None):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="API token expiration must be in the future")
    token, raw_token = create_api_token(
        session,
        target_user=user,
        created_by_user_id=admin_user.user_id,
        name=payload.name,
        expires_at=expires_at,
    )
    log_changes(
        session,
        entity_type="api_token",
        entity_id=token.token_id,
        user_id=admin_user.user_id,
        action="create",
        changes={"user_id": (None, user.user_id), "name": (None, token.name)},
    )
    session.commit()
    session.refresh(token)
    data = ApiTokenRead.model_validate(token).model_dump()
    return ApiTokenIssueResponse(**data, token=raw_token)


@router.delete("/users/{user_id}/api-tokens/{token_id}", response_model=ApiTokenRead)
def revoke_user_api_token(
    user_id: str,
    token_id: str,
    session: Session = Depends(get_db),
    admin_user: User = Depends(require_global_admin),
) -> ApiTokenRead:
    user = _user_or_404(session, user_id)
    _ensure_service_account_target(user)
    token = _token_or_404(session, user.user_id, token_id)
    if api_token_is_active(token):
        token.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add(token)
        log_changes(
            session,
            entity_type="api_token",
            entity_id=token.token_id,
            user_id=admin_user.user_id,
            action="revoke",
            changes={"revoked_at": (None, token.revoked_at.isoformat())},
        )
        session.commit()
        session.refresh(token)
    return token

@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> UserRead:
    global_service_account_update = _is_global_admin(current_user) and _is_service_account_only_update(payload)
    if global_service_account_update:
        user = session.query(User).filter(User.user_id == user_id).first()
    else:
        user = _active_space_user_query(session, space_ctx).filter(User.user_id == user_id).first()
    if not user:
        detail = "User not found" if global_service_account_update else "User not found in active space"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    ensure_actor_can_modify_user(actor=current_user, target=user)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.team_tag is not None:
        user.team_tag = payload.team_tag.strip() or None
    if payload.capacity_fte_month is not None:
        _set_user_capacity_fields(user, capacity_fte_month=payload.capacity_fte_month)
    elif payload.capacity_hours is not None:
        _set_user_capacity_fields(user, capacity_hours=payload.capacity_hours)
    if payload.is_active is not None:
        if user.is_active and not payload.is_active:
            ensure_user_can_be_deactivated(session, user)
        user.is_active = bool(payload.is_active)
    if payload.is_service_account is not None:
        if not _is_global_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global admin required")
        user.is_service_account = bool(payload.is_service_account)
    session.add(user)
    session.commit()
    session.refresh(user)
    _invalidate_user_caches_for_user_memberships(session, user.user_id)
    return user


@router.patch("/users/by-soeid/{soeid}", response_model=UserRead)
def update_user_by_soeid(
    soeid: str,
    payload: UserUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> UserRead:
    soeid_norm = soeid.strip().lower()
    global_service_account_update = _is_global_admin(current_user) and _is_service_account_only_update(payload)
    if global_service_account_update:
        user = session.query(User).filter(User.soeid == soeid_norm).first()
    else:
        user = _active_space_user_query(session, space_ctx).filter(User.soeid == soeid_norm).first()
    if not user:
        detail = "User not found" if global_service_account_update else "User not found in active space"
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    ensure_actor_can_modify_user(actor=current_user, target=user)
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.team_tag is not None:
        user.team_tag = payload.team_tag.strip() or None
    if payload.capacity_fte_month is not None:
        _set_user_capacity_fields(user, capacity_fte_month=payload.capacity_fte_month)
    elif payload.capacity_hours is not None:
        _set_user_capacity_fields(user, capacity_hours=payload.capacity_hours)
    if payload.is_active is not None:
        if user.is_active and not payload.is_active:
            ensure_user_can_be_deactivated(session, user)
        user.is_active = bool(payload.is_active)
    if payload.is_service_account is not None:
        if not _is_global_admin(current_user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global admin required")
        user.is_service_account = bool(payload.is_service_account)
    session.add(user)
    session.commit()
    session.refresh(user)
    _invalidate_user_caches_for_user_memberships(session, user.user_id)
    return user


@router.post("/users/import")
def import_users(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"count": 0, "errors": errors}
    created = 0
    updated = 0
    affected_user_ids: set[str] = set()
    for idx, row in enumerate(rows, start=2):
        soeid = (row.get("soeid") or "").strip().lower()
        display_name = (row.get("display_name") or "").strip()
        team_tag = (row.get("team_tag") or "").strip()
        capacity_fte_raw = (row.get("capacity_fte_month") or "").strip()
        capacity_raw = (row.get("capacity_hours") or "").strip()
        if not soeid or not display_name:
            errors.append(f"Row {idx}: soeid and display_name are required")
            continue
        capacity_fte = 1.0
        if capacity_fte_raw:
            try:
                capacity_fte = max(float(capacity_fte_raw), 0.0)
            except ValueError:
                errors.append(f"Row {idx}: invalid capacity_fte_month '{capacity_fte_raw}'")
                continue
        elif capacity_raw:
            try:
                capacity_fte = max(float(capacity_raw) / _HOURS_PER_FTE_CAPACITY, 0.0)
            except ValueError:
                errors.append(f"Row {idx}: invalid capacity_hours '{capacity_raw}'")
                continue
        user = session.query(User).filter(User.soeid == soeid).first()
        if user:
            try:
                ensure_actor_can_modify_user(actor=current_user, target=user)
            except HTTPException:
                errors.append(f"Row {idx}: only global admin can modify global admin accounts")
                continue
            user.display_name = display_name
            user.team_tag = team_tag or None
            _set_user_capacity_fields(user, capacity_fte_month=capacity_fte)
            user.is_active = True
            session.add(user)
            updated += 1
        else:
            domain = os.getenv("DOMAIN_NAME", "citi.com")
            user = User(
                soeid=soeid,
                email=f"{soeid}@{domain}",
                display_name=display_name,
                password_hash=hash_bootstrap_password(),
                role="user",
                is_active=True,
                team_tag=team_tag or None,
                capacity_hours=max(int(round(capacity_fte * _HOURS_PER_FTE_CAPACITY)), 0),
                capacity_fte_month=round(capacity_fte, 3),
            )
            session.add(user)
            session.flush()
            created += 1
        _ensure_active_membership_for_user(session, user.user_id, space_ctx.space_id)
        affected_user_ids.add(user.user_id)
    session.commit()
    for user_id in affected_user_ids:
        _invalidate_user_caches_for_user_memberships(session, user_id)
    return {"count": created + updated, "created": created, "updated": updated, "errors": errors}


@router.get("/users/export")
def export_users(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    scope_token = make_scope_token("users", space_ctx.space_id)

    def _load():
        users = (
            _active_space_user_query(session, space_ctx)
            .filter(User.is_active == True)
            .order_by(User.display_name.asc())
            .all()
        )
        return [
            {
                "soeid": user.soeid,
                "display_name": user.display_name,
                "team_tag": user.team_tag or "",
                "capacity_fte_month": round(float(user.capacity_fte_month or 0.0), 3),
            }
            for user in users
        ]

    rows = cached_call(
        endpoint="users:export",
        params={},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_USERS_EXPORT_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["soeid", "display_name", "team_tag", "capacity_fte_month"])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="roster.csv"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)




