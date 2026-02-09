import csv
from io import StringIO
import os
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth.auth import hash_password
from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_global_admin,
    require_space_role,
)
from ..models import SpaceMembership, User
from ..schemas import UserRead, UserUpdate
from ..services.audit_log import log_changes
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token
from ..utils import read_csv

router = APIRouter()
_USERS_LIST_TTL_SECONDS = 20
_USERS_EXPORT_TTL_SECONDS = 30
_HOURS_PER_FTE_CAPACITY = 40.0


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _is_global_admin(user: User) -> bool:
    return (user.role or "").strip().lower() == "global_admin"


def _count_active_global_admins(session: Session) -> int:
    return (
        session.query(User)
        .filter(User.is_active.is_(True))
        .filter(User.role == "global_admin")
        .count()
    )


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
            query = query.filter(User.is_active.is_(True))
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
    query = session.query(User).filter(User.role == "global_admin")
    if active_only:
        query = query.filter(User.is_active.is_(True))
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


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: str,
    payload: UserUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> UserRead:
    user = _active_space_user_query(session, space_ctx).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in active space")
    if _is_global_admin(user) and not _is_global_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only global admin can modify global admin accounts",
        )
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.team_tag is not None:
        user.team_tag = payload.team_tag.strip() or None
    if payload.capacity_fte_month is not None:
        _set_user_capacity_fields(user, capacity_fte_month=payload.capacity_fte_month)
    elif payload.capacity_hours is not None:
        _set_user_capacity_fields(user, capacity_hours=payload.capacity_hours)
    if payload.is_active is not None:
        if user.is_active and not payload.is_active and _is_global_admin(user):
            if _count_active_global_admins(session) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least one active global_admin is required",
                )
        user.is_active = bool(payload.is_active)
    session.add(user)
    session.commit()
    session.refresh(user)
    invalidate_space(space_ctx.space_id, ["users"])
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
    user = _active_space_user_query(session, space_ctx).filter(User.soeid == soeid_norm).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found in active space")
    if _is_global_admin(user) and not _is_global_admin(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only global admin can modify global admin accounts",
        )
    if payload.display_name is not None:
        user.display_name = payload.display_name
    if payload.team_tag is not None:
        user.team_tag = payload.team_tag.strip() or None
    if payload.capacity_fte_month is not None:
        _set_user_capacity_fields(user, capacity_fte_month=payload.capacity_fte_month)
    elif payload.capacity_hours is not None:
        _set_user_capacity_fields(user, capacity_hours=payload.capacity_hours)
    if payload.is_active is not None:
        if user.is_active and not payload.is_active and _is_global_admin(user):
            if _count_active_global_admins(session) <= 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least one active global_admin is required",
                )
        user.is_active = bool(payload.is_active)
    session.add(user)
    session.commit()
    session.refresh(user)
    invalidate_space(space_ctx.space_id, ["users"])
    return user


@router.post("/users/import")
def import_users(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"count": 0, "errors": errors}
    created = 0
    updated = 0
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
                password_hash=hash_password("changeme"),
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
    session.commit()
    invalidate_space(space_ctx.space_id, ["users"])
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
            .filter(User.is_active.is_(True))
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
