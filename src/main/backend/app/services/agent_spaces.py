from __future__ import annotations

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models import Space, SpaceMembership, User
from ..schemas.agent import AgentSpaceListRead, AgentSpaceRead
from ..security import security_http_exception
from ..services.agent_pagination import (
    decode_position_cursor,
    encode_position_cursor,
)
from ..services.spaces import is_global_admin_role, normalize_space_kind
from ..utils import normalize_str
from fastapi import status


SPACE_CURSOR_SCOPE = "agent_spaces_v1"


def _base_space_query(session: Session, user: User):
    if is_global_admin_role(user.role):
        return (
            session.query(Space, SpaceMembership.role)
            .outerjoin(
                SpaceMembership,
                and_(
                    SpaceMembership.space_id == Space.space_id,
                    SpaceMembership.user_id == user.user_id,
                    SpaceMembership.status == "active",
                    SpaceMembership.deleted_at.is_(None),
                ),
            )
            .filter(Space.deleted_at.is_(None))
            .filter(Space.is_active)
        )
    return (
        session.query(Space, SpaceMembership.role)
        .join(SpaceMembership, SpaceMembership.space_id == Space.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.status == "active")
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active)
    )


def _space_read(
    space: Space, role: str | None, *, is_global_admin: bool
) -> AgentSpaceRead:
    return AgentSpaceRead(
        space_id=space.space_id,
        name=space.name,
        slug=space.slug,
        space_kind=normalize_space_kind(space.space_kind),
        role="space_admin" if is_global_admin else normalize_str(role) or "member",
        updated_at=space.updated_at,
    )


def list_agent_spaces(
    session: Session,
    user: User,
    *,
    space_id: str | None = None,
    slug: str | None = None,
    name: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
) -> AgentSpaceListRead:
    normalized_space_id = normalize_str(space_id) or None
    normalized_slug = normalize_str(slug).lower() or None
    normalized_name = normalize_str(name) or None
    query = _base_space_query(session, user)
    if normalized_space_id:
        query = query.filter(Space.space_id == normalized_space_id)
    if normalized_slug:
        query = query.filter(Space.slug == normalized_slug)
    if normalized_name:
        query = query.filter(Space.name == normalized_name)

    cursor_filters = {
        "user_id": user.user_id,
        "space_id": normalized_space_id,
        "slug": normalized_slug,
        "name": normalized_name,
    }
    if cursor:
        position = decode_position_cursor(
            cursor,
            scope=SPACE_CURSOR_SCOPE,
            filters=cursor_filters,
        )
        cursor_name = str(position.get("name", ""))
        cursor_id = str(position.get("space_id", ""))
        if not cursor_name or not cursor_id:
            raise security_http_exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="INVALID_CURSOR",
                message="Cursor is invalid for this request",
            )
        query = query.filter(
            or_(
                Space.name > cursor_name,
                and_(Space.name == cursor_name, Space.space_id > cursor_id),
            )
        )

    rows = query.order_by(Space.name.asc(), Space.space_id.asc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last_space = rows[-1][0]
        next_cursor = encode_position_cursor(
            scope=SPACE_CURSOR_SCOPE,
            filters=cursor_filters,
            position={"name": last_space.name, "space_id": last_space.space_id},
        )
    is_global_admin = is_global_admin_role(user.role)
    return AgentSpaceListRead(
        records=[
            _space_read(space, role, is_global_admin=is_global_admin)
            for space, role in rows
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def get_agent_space(session: Session, user: User, space_id: str) -> AgentSpaceRead:
    row = _base_space_query(session, user).filter(Space.space_id == space_id).first()
    if not row:
        raise security_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            code="SPACE_NOT_FOUND",
            message="Space not found",
        )
    space, role = row
    return _space_read(
        space,
        role,
        is_global_admin=is_global_admin_role(user.role),
    )
