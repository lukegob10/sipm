from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import Space, SpaceMembership, User


DEFAULT_SPACE_NAME = "Main"
DEFAULT_SPACE_SLUG = "main"
ACTIVE_SPACE_COOKIE = "active_space_id"


@dataclass(frozen=True)
class SpaceContext:
    space_id: str
    space_name: str
    is_global_admin: bool
    space_role: str


def _normalize_slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in (value or "").strip())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    cleaned = cleaned.strip("-")
    return cleaned or DEFAULT_SPACE_SLUG


def get_or_create_default_space(session: Session) -> Space:
    space = (
        session.query(Space)
        .filter(Space.slug == DEFAULT_SPACE_SLUG)
        .filter(Space.deleted_at.is_(None))
        .first()
    )
    if space:
        if not space.is_active:
            space.is_active = True
            space.archived_at = None
            space.updated_at = datetime.now(timezone.utc)
            session.add(space)
            session.commit()
            session.refresh(space)
        return space

    now = datetime.now(timezone.utc)
    space = Space(
        space_id=str(uuid4()),
        name=DEFAULT_SPACE_NAME,
        slug=DEFAULT_SPACE_SLUG,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(space)
    session.commit()
    session.refresh(space)
    return space


def ensure_space_membership(
    session: Session,
    user: User,
    space_id: str,
    role: str = "member",
    status: str = "active",
) -> SpaceMembership:
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .first()
    )
    if membership:
        changed = False
        if membership.status != status:
            membership.status = status
            changed = True
        if membership.role != role:
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
    if (user.role or "").strip().lower() == "global_admin":
        return (
            session.query(Space)
            .filter(Space.deleted_at.is_(None))
            .filter(Space.is_active.is_(True))
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
        .filter(Space.is_active.is_(True))
        .order_by(Space.name.asc())
        .all()
    )
    return rows


def resolve_active_space_context(
    session: Session,
    user: User,
    requested_space_id: Optional[str],
) -> SpaceContext:
    default_space = get_or_create_default_space(session)
    is_global_admin = (user.role or "").strip().lower() == "global_admin"

    if is_global_admin:
        target = None
        if requested_space_id:
            target = (
                session.query(Space)
                .filter(Space.space_id == requested_space_id)
                .filter(Space.deleted_at.is_(None))
                .filter(Space.is_active.is_(True))
                .first()
            )
        if not target:
            target = default_space
        return SpaceContext(
            space_id=target.space_id,
            space_name=target.name,
            is_global_admin=True,
            space_role="space_admin",
        )

    memberships = (
        session.query(SpaceMembership, Space)
        .join(Space, Space.space_id == SpaceMembership.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.status == "active")
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active.is_(True))
        .order_by(Space.name.asc())
        .all()
    )
    if not memberships:
        ensure_space_membership(session, user, default_space.space_id, role="member")
        memberships = (
            session.query(SpaceMembership, Space)
            .join(Space, Space.space_id == SpaceMembership.space_id)
            .filter(SpaceMembership.user_id == user.user_id)
            .filter(SpaceMembership.status == "active")
            .filter(SpaceMembership.deleted_at.is_(None))
            .filter(Space.deleted_at.is_(None))
            .filter(Space.is_active.is_(True))
            .order_by(Space.name.asc())
            .all()
        )

    selected = None
    if requested_space_id:
        for membership, space in memberships:
            if space.space_id == requested_space_id:
                selected = (membership, space)
                break
    if not selected:
        selected = memberships[0]
    membership, space = selected
    return SpaceContext(
        space_id=space.space_id,
        space_name=space.name,
        is_global_admin=False,
        space_role=membership.role or "member",
    )


def build_space_slug(name: str) -> str:
    return _normalize_slug(name)
