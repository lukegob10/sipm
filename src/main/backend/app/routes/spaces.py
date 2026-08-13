from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import current_space, get_db, require_global_admin, require_user
from ..models import Space, SpaceAccessRequest, SpaceMembership, User
from ..schemas import (
    PersonalSpaceCreate,
    SpaceAccessRequestCreate,
    SpaceAccessRequestRead,
    SpaceAccessRequestReview,
    SpaceCreate,
    SpaceMembershipCreateBySoeid,
    SpaceMembershipCreate,
    SpaceMembershipRead,
    SpaceMembershipUpdate,
    SpaceRead,
    SpaceUpdate,
)
from ..services.spaces import (
    SPACE_KIND_COLLABORATION,
    SPACE_KIND_PERSONAL,
    SpaceContext,
    build_space_slug,
    ensure_space_membership,
    list_user_spaces,
    normalize_space_kind,
)
from ..services.smart_cache import invalidate_space
from ..services.user_admin_guards import lock_space_admin_spaces

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


def _space_or_404_for_membership_mutation(session: Session, space_id: str) -> Space:
    locked_spaces = lock_space_admin_spaces(session, [space_id])
    space = next(
        (
            locked_space
            for locked_space in locked_spaces
            if locked_space.space_id == space_id and locked_space.deleted_at is None
        ),
        None,
    )
    if not space:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Space not found")
    if not space.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reactivate the space before changing memberships",
        )
    return space


def _membership_or_404(session: Session, membership_id: str) -> SpaceMembership:
    row = (
        session.query(SpaceMembership)
        .populate_existing()
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
        .join(User, User.user_id == SpaceMembership.user_id)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(User.is_active)
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
    current_user = session.query(User.is_active).filter(User.user_id == row.user_id).scalar()
    currently_active_admin = (
        row.deleted_at is None
        and current_role == "space_admin"
        and current_status == "active"
        and bool(current_user)
    )
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


def _validate_space_name(raw_name: str | None) -> str:
    name = str(raw_name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Space name is required")
    return name


def _space_kind_label(space: Space) -> str:
    return normalize_space_kind(getattr(space, "space_kind", None))


def _validate_collaboration_space(space: Space) -> None:
    if _space_kind_label(space) != SPACE_KIND_COLLABORATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only collaboration spaces support access requests",
        )
    if not space.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Space is archived")


def _ensure_personal_space_allows_target(space: Space, user_id: str) -> None:
    if _space_kind_label(space) != SPACE_KIND_PERSONAL:
        return
    if space.owner_user_id != user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Personal spaces cannot add members")


def _ensure_request_reviewer(ctx: SpaceContext, request_row: SpaceAccessRequest) -> None:
    if ctx.is_global_admin:
        return
    if ctx.space_id != request_row.space_id or _normalize_space_role(ctx.space_role) != "space_admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Space admin required")


def _space_conflict_detail(exc: IntegrityError) -> str | None:
    orig_text = str(getattr(exc, "orig", "")).lower()
    text = " ".join(
        [
            str(exc),
            orig_text,
            str(getattr(exc, "statement", "")),
        ]
    ).lower()
    if "tb_ta_pm_spaces.name" in orig_text or ".name" in orig_text:
        return "Space name already exists"
    if "tb_ta_pm_spaces.slug" in orig_text or ".slug" in orig_text:
        return "Space slug already exists"
    if "uix_space_slug" in text:
        return "Space slug already exists"
    if "uix_space_name" in text:
        return "Space name already exists"
    has_unique_marker = any(
        marker in text
        for marker in (
            "ora-03301",
            "ora-00001",
            "unique constraint",
            "unique constraint failed",
        )
    )
    if not has_unique_marker or ("tb_ta_pm_spaces" not in text and "space" not in text):
        return None
    if "slug" in text:
        return "Space slug already exists"
    if "name" in text:
        return "Space name already exists"
    return "Space already exists"


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


def _serialize_access_request(session: Session, row: SpaceAccessRequest) -> SpaceAccessRequestRead:
    space = session.query(Space).filter(Space.space_id == row.space_id).first()
    requester = session.query(User).filter(User.user_id == row.requester_user_id).first()
    return SpaceAccessRequestRead(
        request_id=row.request_id,
        space_id=row.space_id,
        space_name=space.name if space else None,
        space_slug=space.slug if space else None,
        requester_user_id=row.requester_user_id,
        requester_soeid=requester.soeid if requester else None,
        requester_display_name=requester.display_name if requester else None,
        requested_role=_normalize_space_role(row.requested_role),
        status=row.status,
        decided_by_user_id=row.decided_by_user_id,
        decided_at=row.decided_at,
        decision_note=row.decision_note,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _serialize_access_requests(session: Session, rows: list[SpaceAccessRequest]) -> list[SpaceAccessRequestRead]:
    return [_serialize_access_request(session, row) for row in rows]


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


@router.get("/spaces/requestable", response_model=list[SpaceRead])
def list_requestable_spaces(
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    _ctx: SpaceContext = Depends(current_space),
) -> list[SpaceRead]:
    active_membership_space_ids = {
        row.space_id
        for row in (
            session.query(SpaceMembership.space_id)
            .filter(SpaceMembership.user_id == current_user.user_id)
            .filter(SpaceMembership.status == "active")
            .filter(SpaceMembership.deleted_at.is_(None))
            .all()
        )
    }
    return (
        session.query(Space)
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active)
        .filter(Space.space_kind == SPACE_KIND_COLLABORATION)
        .filter(~Space.space_id.in_(active_membership_space_ids) if active_membership_space_ids else True)
        .order_by(Space.name.asc())
        .all()
    )


@router.post("/spaces/personal", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def create_personal_space(
    payload: PersonalSpaceCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    _ctx: SpaceContext = Depends(current_space),
) -> SpaceRead:
    existing = (
        session.query(Space)
        .filter(Space.owner_user_id == current_user.user_id)
        .filter(Space.space_kind == SPACE_KIND_PERSONAL)
        .filter(Space.deleted_at.is_(None))
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has a personal space")

    user_token = (current_user.soeid or current_user.display_name or current_user.user_id).strip()
    base_name = _validate_space_name(f"{user_token.upper()} Personal")
    name = base_name
    name_suffix = 2
    while (
        session.query(Space)
        .filter(Space.name == name)
        .filter(Space.deleted_at.is_(None))
        .first()
    ):
        name = f"{base_name} {name_suffix}"
        name_suffix += 1
    slug_seed = f"{current_user.soeid or current_user.user_id}-personal"
    slug = build_space_slug(slug_seed)
    suffix = 2
    while (
        session.query(Space)
        .filter(Space.slug == slug)
        .filter(Space.deleted_at.is_(None))
        .first()
    ):
        slug = build_space_slug(f"{slug_seed}-{suffix}")
        suffix += 1

    now = datetime.now(timezone.utc)
    space = Space(
        space_id=str(uuid4()),
        name=name,
        slug=slug,
        is_active=True,
        space_kind=SPACE_KIND_PERSONAL,
        owner_user_id=current_user.user_id,
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(space)
        session.commit()
        session.refresh(space)
    except IntegrityError as exc:
        session.rollback()
        detail = (
            "User already has a personal space"
            if "uix_space_owner_kind" in str(exc).lower()
            else (_space_conflict_detail(exc) or "User already has a personal space")
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc

    ensure_space_membership(session, current_user, space.space_id, role="space_admin")
    return space


@router.get("/spaces/access-requests", response_model=list[SpaceAccessRequestRead])
def list_my_space_access_requests(
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    _ctx: SpaceContext = Depends(current_space),
) -> list[SpaceAccessRequestRead]:
    rows = (
        session.query(SpaceAccessRequest)
        .filter(SpaceAccessRequest.requester_user_id == current_user.user_id)
        .order_by(SpaceAccessRequest.created_at.desc())
        .all()
    )
    return _serialize_access_requests(session, rows)


@router.get("/spaces/access-requests/reviewable", response_model=list[SpaceAccessRequestRead])
def list_reviewable_space_access_requests(
    session: Session = Depends(get_db),
    _current_user: User = Depends(require_user),
    ctx: SpaceContext = Depends(current_space),
) -> list[SpaceAccessRequestRead]:
    query = (
        session.query(SpaceAccessRequest)
        .join(Space, Space.space_id == SpaceAccessRequest.space_id)
        .filter(SpaceAccessRequest.status == "pending")
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active)
        .filter(Space.space_kind == SPACE_KIND_COLLABORATION)
    )
    if not ctx.is_global_admin:
        if _normalize_space_role(ctx.space_role) != "space_admin":
            return []
        query = query.filter(SpaceAccessRequest.space_id == ctx.space_id)
    rows = query.order_by(SpaceAccessRequest.created_at.asc()).all()
    return _serialize_access_requests(session, rows)


@router.post(
    "/spaces/{space_id}/access-requests",
    response_model=SpaceAccessRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def request_space_access(
    space_id: str,
    payload: SpaceAccessRequestCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    _ctx: SpaceContext = Depends(current_space),
) -> SpaceAccessRequestRead:
    target_space = _space_or_404(session, space_id)
    _validate_collaboration_space(target_space)
    requested_role = _validate_space_role(payload.requested_role)
    existing_membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == current_user.user_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .first()
    )
    if existing_membership:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has access to this space")

    pending = (
        session.query(SpaceAccessRequest)
        .filter(SpaceAccessRequest.space_id == space_id)
        .filter(SpaceAccessRequest.requester_user_id == current_user.user_id)
        .filter(SpaceAccessRequest.status == "pending")
        .first()
    )
    if pending:
        return _serialize_access_request(session, pending)

    now = datetime.now(timezone.utc)
    row = SpaceAccessRequest(
        request_id=str(uuid4()),
        space_id=space_id,
        requester_user_id=current_user.user_id,
        requested_role=requested_role,
        status="pending",
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize_access_request(session, row)


@router.delete("/spaces/access-requests/{request_id}", response_model=SpaceAccessRequestRead)
def cancel_space_access_request(
    request_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    _ctx: SpaceContext = Depends(current_space),
) -> SpaceAccessRequestRead:
    row = (
        session.query(SpaceAccessRequest)
        .filter(SpaceAccessRequest.request_id == request_id)
        .first()
    )
    if not row or row.requester_user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be canceled")
    row.status = "canceled"
    row.decided_by_user_id = current_user.user_id
    row.decided_at = datetime.now(timezone.utc)
    row.updated_at = row.decided_at
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize_access_request(session, row)


@router.post("/spaces/access-requests/{request_id}/approve", response_model=SpaceAccessRequestRead)
def approve_space_access_request(
    request_id: str,
    payload: SpaceAccessRequestReview | None = None,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    ctx: SpaceContext = Depends(current_space),
) -> SpaceAccessRequestRead:
    row = session.query(SpaceAccessRequest).filter(SpaceAccessRequest.request_id == request_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
    _ensure_request_reviewer(ctx, row)
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be approved")
    target_space = _space_or_404(session, row.space_id)
    _validate_collaboration_space(target_space)
    requester = session.query(User).filter(User.user_id == row.requester_user_id).first()
    if not requester or not requester.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Requester is not active")
    ensure_space_membership(session, requester, row.space_id, role=_normalize_space_role(row.requested_role))
    row.status = "approved"
    row.decided_by_user_id = current_user.user_id
    row.decided_at = datetime.now(timezone.utc)
    row.decision_note = payload.decision_note if payload else None
    row.updated_at = row.decided_at
    session.add(row)
    session.commit()
    session.refresh(row)
    _invalidate_space_membership_views(row.space_id)
    return _serialize_access_request(session, row)


@router.post("/spaces/access-requests/{request_id}/reject", response_model=SpaceAccessRequestRead)
def reject_space_access_request(
    request_id: str,
    payload: SpaceAccessRequestReview | None = None,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_user),
    ctx: SpaceContext = Depends(current_space),
) -> SpaceAccessRequestRead:
    row = session.query(SpaceAccessRequest).filter(SpaceAccessRequest.request_id == request_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access request not found")
    _ensure_request_reviewer(ctx, row)
    if row.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending requests can be rejected")
    row.status = "rejected"
    row.decided_by_user_id = current_user.user_id
    row.decided_at = datetime.now(timezone.utc)
    row.decision_note = payload.decision_note if payload else None
    row.updated_at = row.decided_at
    session.add(row)
    session.commit()
    session.refresh(row)
    return _serialize_access_request(session, row)


@router.post("/spaces", response_model=SpaceRead, status_code=status.HTTP_201_CREATED)
def create_space(
    payload: SpaceCreate,
    session: Session = Depends(get_db),
    _admin: User = Depends(require_global_admin),
) -> SpaceRead:
    now = datetime.now(timezone.utc)
    name = _validate_space_name(payload.name)
    slug = build_space_slug(payload.slug or name)
    existing = session.query(Space).filter(Space.slug == slug).filter(Space.deleted_at.is_(None)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Space slug already exists")
    space = Space(
        space_id=str(uuid4()),
        name=name,
        slug=slug,
        is_active=True,
        space_kind=SPACE_KIND_COLLABORATION,
        owner_user_id=None,
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(space)
        session.commit()
        session.refresh(space)
    except IntegrityError as exc:
        session.rollback()
        detail = _space_conflict_detail(exc)
        if detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise
    return space


@router.patch("/spaces/{space_id}", response_model=SpaceRead)
def update_space(
    space_id: str,
    payload: SpaceUpdate,
    session: Session = Depends(get_db),
    _current_user: User = Depends(require_user),
    ctx=Depends(current_space),
) -> SpaceRead:
    space = _space_or_404(session, space_id)
    wants_admin_only_change = payload.name is not None or payload.is_active is not None
    if wants_admin_only_change and not ctx.is_global_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Global admin required")
    _ensure_space_admin_access(ctx, space_id)
    if payload.name is not None:
        space.name = _validate_space_name(payload.name)
    if payload.is_active is not None:
        space.is_active = bool(payload.is_active)
        if not space.is_active:
            space.archived_at = datetime.now(timezone.utc)
        else:
            space.archived_at = None
    if payload.public_program_dashboard_enabled is not None:
        if not space.is_active and bool(payload.public_program_dashboard_enabled):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reactivate the space before exposing the public dashboard",
            )
        space.public_program_dashboard_enabled = bool(payload.public_program_dashboard_enabled)
    space.updated_at = datetime.now(timezone.utc)
    try:
        session.add(space)
        session.commit()
        session.refresh(space)
    except IntegrityError as exc:
        session.rollback()
        detail = _space_conflict_detail(exc)
        if detail:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail) from exc
        raise
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
    space = _space_or_404_for_membership_mutation(session, space_id)
    user = session.query(User).filter(User.user_id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _ensure_personal_space_allows_target(space, user.user_id)
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
    space = _space_or_404_for_membership_mutation(session, space_id)
    soeid_norm = (payload.soeid or "").strip().lower()
    if not soeid_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="SOEID is required")
    user = session.query(User).filter(User.soeid == soeid_norm).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _ensure_personal_space_allows_target(space, user.user_id)
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
    _space_or_404_for_membership_mutation(session, space_id)
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
    _space_or_404_for_membership_mutation(session, space_id)
    row = _membership_or_404(session, membership_id)
    if row.space_id != space_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Membership does not belong to space")
    _ensure_space_retains_admin(session, row, deleting=True)
    row.deleted_at = datetime.now(timezone.utc)
    session.add(row)
    session.commit()
    _invalidate_space_membership_views(space_id)
    return None
