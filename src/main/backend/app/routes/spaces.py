from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import current_space, get_db, require_global_admin, require_user
from ..models import Space, SpaceMembership, User
from ..schemas import (
    SpaceCreate,
    SpaceMembershipCreateBySoeid,
    SpaceMembershipCreate,
    SpaceMembershipRead,
    SpaceMembershipUpdate,
    SpaceRead,
    SpaceUpdate,
)
from ..services.spaces import build_space_slug, list_user_spaces
from ..services.smart_cache import invalidate_space

router = APIRouter()


def _normalize_space_role(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or "member"


def _space_or_404(session: Session, space_id: str) -> Space:
    space = (
        session.query(Space)
        .filter(Space.space_id == space_id)
        .filter(Space.deleted_at.is_(None))
        .first()
    )
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    return space


def _membership_or_404(session: Session, membership_id: str) -> SpaceMembership:
    row = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.membership_id == membership_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .first()
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Membership not found")
    return row


def _count_active_space_admins(session: Session, space_id: str, exclude_membership_id: str | None = None) -> int:
    normalized_role = func.lower(
        func.replace(
            func.replace(func.coalesce(SpaceMembership.role, ""), "-", "_"),
            " ",
            "_",
        )
    )
    query = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(normalized_role == "space_admin")
    )
    if exclude_membership_id:
        query = query.filter(SpaceMembership.membership_id != exclude_membership_id)
    return query.count()


def _ensure_space_retains_admin(
    session: Session,
    row: SpaceMembership,
    *,
    next_role: str | None = None,
    next_status: str | None = None,
    deleting: bool = False,
) -> None:
    current_role = _normalize_space_role(row.role)
    current_status = (row.status or "").strip().lower()
    currently_active_admin = row.deleted_at is None and current_role == "space_admin" and current_status == "active"
    if not currently_active_admin:
        return

    role_after = _normalize_space_role(next_role if next_role is not None else current_role)
    status_after = (next_status if next_status is not None else current_status).strip().lower()
    remains_active_admin = (not deleting) and role_after == "space_admin" and status_after == "active"
    if remains_active_admin:
        return

    remaining = _count_active_space_admins(session, row.space_id, exclude_membership_id=row.membership_id)
    if remaining == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Space must retain at least one active space_admin",
        )


def _ensure_space_admin_access(ctx, target_space_id: str) -> None:
    if ctx.is_global_admin:
        return
    if ctx.space_id != target_space_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot manage another space")
    if _normalize_space_role(ctx.space_role) != "space_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Space admin required")


def _validate_space_role(raw_role: str | None) -> str:
    role = _normalize_space_role(raw_role)
    if role not in {"member", "space_admin"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid space role")
    return role


def _validate_membership_status(raw_status: str | None) -> str:
    status_val = (raw_status or "active").strip().lower()
    if status_val not in {"active", "inactive"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid membership status")
    return status_val


def _serialize_memberships(session: Session, rows: list[SpaceMembership]) -> list[SpaceMembershipRead]:
    if not rows:
        return []
    user_ids = sorted({row.user_id for row in rows if row.user_id})
    users_by_id: dict[str, User] = {}
    if user_ids:
        users_by_id = {
            user.user_id: user
            for user in session.query(User).filter(User.user_id.in_(user_ids)).all()
        }
    output: list[SpaceMembershipRead] = []
    for row in rows:
        user = users_by_id.get(row.user_id)
        output.append(
            SpaceMembershipRead(
                membership_id=row.membership_id,
                space_id=row.space_id,
                user_id=row.user_id,
                user_soeid=user.soeid if user else None,
                user_display_name=user.display_name if user else None,
                user_email=user.email if user else None,
                role=_normalize_space_role(row.role),
                status=row.status,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        )
    return output


def _serialize_membership(session: Session, row: SpaceMembership) -> SpaceMembershipRead:
    return _serialize_memberships(session, [row])[0]


def _invalidate_space_membership_views(space_id: str) -> None:
    invalidate_space(space_id, ["users"])


def _create_or_restore_membership(
    session: Session,
    *,
    space_id: str,
    user_id: str,
    role: str,
    status_val: str,
) -> SpaceMembership:
    existing = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == user_id)
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing:
        if existing.deleted_at is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Membership already exists")
        existing.deleted_at = None
        existing.role = role
        existing.status = status_val
        existing.updated_at = now
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    row = SpaceMembership(
        membership_id=str(uuid4()),
        space_id=space_id,
        user_id=user_id,
        role=role,
        status=status_val,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/spaces", response_model=list[SpaceRead])
def list_spaces(
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
) -> list[SpaceRead]:
    return list(list_user_spaces(session, current_user))


@router.post("/spaces", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def create_space(
    payload: SpaceCreate,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> SpaceRead:
    now = datetime.now(timezone.utc)
    slug = build_space_slug(payload.slug or payload.name)
    existing = session.query(Space).filter(Space.slug == slug).filter(Space.deleted_at.is_(None)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Space slug already exists")
    space = Space(
        space_id=str(uuid4()),
        name=payload.name.strip(),
        slug=slug,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(space)
    session.commit()
    session.refresh(space)
    return space


@router.patch("/spaces/{space_id}", response_model=SpaceRead)
def update_space(
    space_id: str,
    payload: SpaceUpdate,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> SpaceRead:
    space = _space_or_404(session, space_id)
    if payload.name is not None:
        space.name = payload.name.strip() or space.name
    if payload.is_active is not None:
        space.is_active = bool(payload.is_active)
        if not space.is_active:
            space.archived_at = datetime.now(timezone.utc)
        else:
            space.archived_at = None
    space.updated_at = datetime.now(timezone.utc)
    session.add(space)
    session.commit()
    session.refresh(space)
    return space


@router.get("/spaces/{space_id}/members", response_model=list[SpaceMembershipRead])
def list_space_members(
    space_id: str,
    session: Session = Depends(get_db),
    ctx=Depends(current_space),
) -> list[SpaceMembershipRead]:
    _ensure_space_admin_access(ctx, space_id)
    _space_or_404(session, space_id)
    rows = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .order_by(SpaceMembership.created_at.asc())
        .all()
    )
    return _serialize_memberships(session, rows)


@router.post("/spaces/{space_id}/members", response_model=SpaceMembershipRead, status_code=status.HTTP_201_CREATED)
def create_space_member(
    space_id: str,
    payload: SpaceMembershipCreate,
    session: Session = Depends(get_db),
    ctx=Depends(current_space),
) -> SpaceMembershipRead:
    _ensure_space_admin_access(ctx, space_id)
    _space_or_404(session, space_id)
    user = session.query(User).filter(User.user_id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    role = _validate_space_role(payload.role)
    status_val = _validate_membership_status(payload.status)
    row = _create_or_restore_membership(
        session,
        space_id=space_id,
        user_id=payload.user_id,
        role=role,
        status_val=status_val,
    )
    _invalidate_space_membership_views(space_id)
    return _serialize_membership(session, row)


@router.post("/spaces/{space_id}/members/by-soeid", response_model=SpaceMembershipRead, status_code=status.HTTP_201_CREATED)
def create_space_member_by_soeid(
    space_id: str,
    payload: SpaceMembershipCreateBySoeid,
    session: Session = Depends(get_db),
    ctx=Depends(current_space),
) -> SpaceMembershipRead:
    _ensure_space_admin_access(ctx, space_id)
    _space_or_404(session, space_id)
    soeid_norm = (payload.soeid or "").strip().lower()
    if not soeid_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SOEID is required")
    user = session.query(User).filter(User.soeid == soeid_norm).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    role = _validate_space_role(payload.role)
    status_val = _validate_membership_status(payload.status)
    row = _create_or_restore_membership(
        session,
        space_id=space_id,
        user_id=user.user_id,
        role=role,
        status_val=status_val,
    )
    _invalidate_space_membership_views(space_id)
    return _serialize_membership(session, row)


@router.patch("/spaces/{space_id}/members/{membership_id}", response_model=SpaceMembershipRead)
def update_space_member(
    space_id: str,
    membership_id: str,
    payload: SpaceMembershipUpdate,
    session: Session = Depends(get_db),
    ctx=Depends(current_space),
) -> SpaceMembershipRead:
    _ensure_space_admin_access(ctx, space_id)
    _space_or_404(session, space_id)
    row = _membership_or_404(session, membership_id)
    if row.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Membership does not belong to space")
    next_role = None
    if payload.role is not None:
        next_role = _validate_space_role(payload.role)
    next_status = None
    if payload.status is not None:
        next_status = _validate_membership_status(payload.status)

    _ensure_space_retains_admin(session, row, next_role=next_role, next_status=next_status)
    if next_role is not None:
        row.role = next_role
    if next_status is not None:
        row.status = next_status
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    session.refresh(row)
    _invalidate_space_membership_views(space_id)
    return _serialize_membership(session, row)


@router.delete("/spaces/{space_id}/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_space_member(
    space_id: str,
    membership_id: str,
    session: Session = Depends(get_db),
    ctx=Depends(current_space),
):
    _ensure_space_admin_access(ctx, space_id)
    _space_or_404(session, space_id)
    row = _membership_or_404(session, membership_id)
    if row.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Membership does not belong to space")
    _ensure_space_retains_admin(session, row, deleting=True)
    row.deleted_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    _invalidate_space_membership_views(space_id)
    return None
