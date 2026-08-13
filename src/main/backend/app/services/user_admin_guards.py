from __future__ import annotations

from collections.abc import Iterable

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.sql import Select
from sqlalchemy.orm import Session

from ..models import Space, SpaceMembership, User
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


def _sorted_space_ids(space_ids: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({space_id for space_id in space_ids if space_id}))


def _space_admin_lock_statement(space_ids: Iterable[str]) -> Select:
    ordered_space_ids = _sorted_space_ids(space_ids)
    return (
        select(Space)
        .where(Space.space_id.in_(ordered_space_ids))
        .order_by(Space.space_id.asc())
        .with_for_update()
    )


def lock_space_admin_spaces(session: Session, space_ids: Iterable[str]) -> list[Space]:
    """Serialize changes that could remove a space's final active administrator."""
    ordered_space_ids = _sorted_space_ids(space_ids)
    if not ordered_space_ids:
        return []

    if session.get_bind().dialect.name == "sqlite":
        # SQLite drops SELECT ... FOR UPDATE. A no-op sentinel update starts a
        # write transaction so separate local/test sessions still serialize.
        session.execute(
            update(Space)
            .where(Space.space_id.in_(ordered_space_ids))
            .values(
                {
                    Space.space_id: Space.space_id,
                    Space.updated_at: Space.updated_at,
                }
            )
            .execution_options(synchronize_session=False)
        )

    statement = _space_admin_lock_statement(ordered_space_ids).execution_options(populate_existing=True)
    return list(session.scalars(statement).all())


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


def _membership_space_ids(session: Session, user: User) -> list[str]:
    rows = (
        session.query(SpaceMembership.space_id)
        .filter(SpaceMembership.user_id == user.user_id)
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

    # Include inactive and soft-deleted memberships when selecting sentinels so
    # a concurrent restore/promotion cannot bypass the same space-row lock.
    lock_space_admin_spaces(session, _membership_space_ids(session, user))

    # Re-read after acquiring the locks. The User instance and its memberships
    # may have been loaded before another transaction completed.
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
