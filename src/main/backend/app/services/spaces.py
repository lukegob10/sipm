from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import status

from ..models import Space, SpaceMembership, User
from ..security import security_http_exception


DEFAULT_SPACE_NAME = "Home"
DEFAULT_SPACE_SLUG = "home"
ACTIVE_SPACE_COOKIE = "active_space_id"
SPACE_KIND_COLLABORATION = "collaboration"
SPACE_KIND_LOBBY = "lobby"
SPACE_KIND_PERSONAL = "personal"
SPACE_KINDS = {SPACE_KIND_COLLABORATION, SPACE_KIND_LOBBY, SPACE_KIND_PERSONAL}


@dataclass(frozen=True)
class SpaceContext:
    space_id: str
    space_name: str
    is_global_admin: bool
    space_role: str
    space_kind: str = SPACE_KIND_COLLABORATION
    owner_user_id: str | None = None


def _normalize_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "").strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned or DEFAULT_SPACE_SLUG


def _normalize_space_role(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized or "member"


def normalize_space_kind(value: str | None) -> str:
    normalized = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return normalized if normalized in SPACE_KINDS else SPACE_KIND_COLLABORATION


def normalize_global_role(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def is_global_admin_role(value: str | None) -> bool:
    return normalize_global_role(value) == "global_admin"


def _ensure_lobby_shape(session: Session, space: Space, *, commit: bool = True) -> Space:
    changed = False
    if space.name != DEFAULT_SPACE_NAME:
        name_conflict = (
            session.query(Space)
            .filter(Space.name == DEFAULT_SPACE_NAME)
            .filter(Space.space_id != space.space_id)
            .filter(Space.deleted_at.is_(None))
            .first()
        )
        if not name_conflict:
            space.name = DEFAULT_SPACE_NAME
            changed = True
    if normalize_space_kind(getattr(space, "space_kind", None)) != SPACE_KIND_LOBBY:
        space.space_kind = SPACE_KIND_LOBBY
        changed = True
    if getattr(space, "owner_user_id", None) is not None:
        space.owner_user_id = None
        changed = True
    if not space.is_active:
        space.is_active = True
        space.archived_at = None
        changed = True
    if changed:
        space.updated_at = datetime.now(timezone.utc)
        session.add(space)
        if commit:
            session.commit()
            session.refresh(space)
    return space


def get_or_create_default_space(session: Session, *, commit: bool = True) -> Space:
    space = (
        session.query(Space)
        .filter(Space.slug == DEFAULT_SPACE_SLUG)
        .filter(Space.deleted_at.is_(None))
        .first()
    )
    if space:
        return _ensure_lobby_shape(session, space, commit=commit)

    now = datetime.now(timezone.utc)
    space = Space(
        space_id=str(uuid4()),
        name=DEFAULT_SPACE_NAME,
        slug=DEFAULT_SPACE_SLUG,
        is_active=True,
        space_kind=SPACE_KIND_LOBBY,
        owner_user_id=None,
        created_at=now,
        updated_at=now,
    )
    if not commit:
        session.add(space)
        return space

    try:
        session.add(space)
        session.commit()
        session.refresh(space)
        return space
    except IntegrityError:
        session.rollback()
        existing = (
            session.query(Space)
            .filter(Space.slug == DEFAULT_SPACE_SLUG)
            .filter(Space.deleted_at.is_(None))
            .first()
        )
        if existing:
            return _ensure_lobby_shape(session, existing)
        raise


def ensure_space_membership(
    session: Session,
    user: User,
    space_id: str,
    role: str = "member",
    status: str = "active",
) -> SpaceMembership:
    role = _normalize_space_role(role)
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .first()
    )
    if membership:
        changed = False
        if membership.deleted_at is not None:
            membership.deleted_at = None
            changed = True
        if membership.status != status:
            membership.status = status
            changed = True
        if _normalize_space_role(membership.role) != role:
            membership.role = role
            changed = True
        if changed:
            membership.updated_at = datetime.now(timezone.utc)
            session.add(membership)
            session.commit()
            session.refresh(membership)
        return membership

    now = datetime.now(timezone.utc)
    membership = SpaceMembership(
        membership_id=str(uuid4()),
        space_id=space_id,
        user_id=user.user_id,
        role=role,
        status=status,
        created_at=now,
        updated_at=now,
    )
    session.add(membership)
    session.commit()
    session.refresh(membership)
    return membership


def list_user_spaces(session: Session, user: User) -> Iterable[Space]:
    if is_global_admin_role(user.role):
        return (
            session.query(Space)
            .filter(Space.deleted_at.is_(None))
            .filter(Space.is_active)
            .filter((Space.space_kind != SPACE_KIND_PERSONAL) | (Space.owner_user_id == user.user_id))
            .order_by(Space.name.asc())
            .all()
        )

    rows = (
        session.query(Space)
        .join(SpaceMembership, SpaceMembership.space_id == Space.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.status == "active")
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active)
        .order_by(Space.name.asc())
        .all()
    )
    return rows


def resolve_active_space_context(
    session: Session,
    user: User,
    requested_space_id: Optional[str],
) -> SpaceContext:
    is_global_admin = is_global_admin_role(user.role)

    if is_global_admin:
        default_space = get_or_create_default_space(session)
        target = None
        if requested_space_id:
            target = (
                session.query(Space)
                .filter(Space.space_id == requested_space_id)
                .filter(Space.deleted_at.is_(None))
                .filter(Space.is_active)
                .first()
            )
        if not target:
            target = default_space
        return SpaceContext(
            space_id=target.space_id,
            space_name=target.name,
            is_global_admin=True,
            space_role="space_admin",
            space_kind=normalize_space_kind(getattr(target, "space_kind", None)),
            owner_user_id=getattr(target, "owner_user_id", None),
        )

    memberships = (
        session.query(SpaceMembership, Space)
        .join(Space, Space.space_id == SpaceMembership.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.status == "active")
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active)
        .order_by(Space.name.asc())
        .all()
    )
    if not memberships:
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="NO_ACTIVE_SPACE",
            message="No active space is available for this user",
        )

    selected = None
    if requested_space_id:
        for membership, space in memberships:
            if space.space_id == requested_space_id:
                selected = (membership, space)
                break
    if not selected:
        selected = next(
            (
                (membership, space)
                for membership, space in memberships
                if normalize_space_kind(getattr(space, "space_kind", None)) != SPACE_KIND_LOBBY
            ),
            memberships[0],
        )
    membership, space = selected
    return SpaceContext(
        space_id=space.space_id,
        space_name=space.name,
        is_global_admin=False,
        space_role=_normalize_space_role(membership.role),
        space_kind=normalize_space_kind(getattr(space, "space_kind", None)),
        owner_user_id=getattr(space, "owner_user_id", None),
    )


def build_space_slug(name: str) -> str:
    return _normalize_slug(name)
