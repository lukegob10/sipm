from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import SpaceMembership, User
from .spaces import is_global_admin_role

LAST_GLOBAL_ADMIN_ERROR = "At least one active global_admin is required"
LAST_SPACE_ADMIN_ERROR = "Space must retain at least one active space_admin"


def is_global_admin_user(user: User) -> bool:
    return is_global_admin_role(user.role)


def _normalized_role_expr(column):
    return func.lower(
        func.replace(
            func.replace(func.coalesce(column, ""), "-", "_"),
            " ",
            "_",
        )
    )


def normalized_global_role_expr():
    return _normalized_role_expr(User.role)


def normalized_space_admin_role_expr():
    return _normalized_role_expr(SpaceMembership.role)


def count_active_global_admins(session: Session) -> int:
    return (
        session.query(User)
        .filter(User.is_active)
        .filter(normalized_global_role_expr() == "global_admin")
        .count()
    )


def _count_other_active_space_admins(session: Session, *, space_id: str, exclude_user_id: str) -> int:
    return (
        session.query(SpaceMembership)
        .join(User, User.user_id == SpaceMembership.user_id)
        .filter(SpaceMembership.space_id == space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(User.is_active)
        .filter(SpaceMembership.user_id != exclude_user_id)
        .filter(normalized_space_admin_role_expr() == "space_admin")
        .count()
    )


def _space_id_from_row(row) -> str | None:
    if isinstance(row, tuple):
        return row[0]
    return getattr(row, "space_id", None)


def _active_space_admin_space_ids(session: Session, user: User) -> list[str]:
    rows = (
        session.query(SpaceMembership.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(normalized_space_admin_role_expr() == "space_admin")
        .distinct()
        .all()
    )
    return [space_id for row in rows if (space_id := _space_id_from_row(row))]


def ensure_actor_can_modify_user(*, actor: User, target: User) -> None:
    if is_global_admin_user(target) and not is_global_admin_user(actor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only global admin can modify global admin accounts",
        )


def ensure_user_can_be_deactivated(session: Session, user: User) -> None:
    if not user.is_active:
        return
    if is_global_admin_user(user) and count_active_global_admins(session) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=LAST_GLOBAL_ADMIN_ERROR,
        )

    for space_id in _active_space_admin_space_ids(session, user):
        if (
            _count_other_active_space_admins(
                session,
                space_id=space_id,
                exclude_user_id=user.user_id,
            )
            == 0
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=LAST_SPACE_ADMIN_ERROR,
            )
