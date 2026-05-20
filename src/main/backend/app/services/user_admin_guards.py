from __future__ import annotations

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import SpaceMembership, User
from ..security import security_http_exception
from .spaces import is_global_admin_role


def is_global_admin_user(user: User) -> bool:
    return is_global_admin_role(user.role)


def normalized_global_role_expr():
    return func.lower(
        func.replace(
            func.replace(func.coalesce(User.role, ""), "-", "_"),
            " ",
            "_",
        )
    )


def normalized_space_admin_role_expr():
    return func.lower(
        func.replace(
            func.replace(func.coalesce(SpaceMembership.role, ""), "-", "_"),
            " ",
            "_",
        )
    )


def count_active_global_admins(session: Session) -> int:
    return (
        session.query(User)
        .filter(User.is_active == True)
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
        .filter(User.is_active == True)
        .filter(SpaceMembership.user_id != exclude_user_id)
        .filter(normalized_space_admin_role_expr() == "space_admin")
        .count()
    )


def ensure_actor_can_modify_user(*, actor: User, target: User) -> None:
    if is_global_admin_user(target) and not is_global_admin_user(actor):
        raise security_http_exception(
            status_code=status.HTTP_403_FORBIDDEN,
            code="GLOBAL_ADMIN_REQUIRED",
            message="Only global admin can modify global admin accounts",
        )


def ensure_user_can_be_deactivated(session: Session, user: User) -> None:
    if not user.is_active:
        return
    if is_global_admin_user(user) and count_active_global_admins(session) <= 1:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="LAST_GLOBAL_ADMIN",
            message="At least one active global_admin is required",
        )

    rows = (
        session.query(SpaceMembership.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(normalized_space_admin_role_expr() == "space_admin")
        .distinct()
        .all()
    )
    for row in rows:
        space_id = row[0] if isinstance(row, tuple) else getattr(row, "space_id", None)
        if not space_id:
            continue
        if _count_other_active_space_admins(session, space_id=space_id, exclude_user_id=user.user_id) == 0:
            raise security_http_exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="LAST_SPACE_ADMIN",
                message="Space must retain at least one active space_admin",
            )
