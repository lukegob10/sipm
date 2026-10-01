from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import Program, Project, Solution, Task, User
from .audit_log import log_changes
from .spaces import SpaceContext


def deleted_work_item_name(name: str, entity_id: str, deleted_at: datetime) -> str:
    timestamp = (
        deleted_at.replace(tzinfo=timezone.utc)
        if deleted_at.tzinfo is None
        else deleted_at.astimezone(timezone.utc)
    )
    suffix = f" [deleted {timestamp.strftime('%Y%m%dT%H%M%SZ')} {entity_id}]"
    base = name.strip()
    return f"{base[:max(1, 255 - len(suffix))]}{suffix}"


def release_deleted_work_item_names(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    *,
    entity: str,
    name: str,
    parent_id: str | None = None,
    version: str | None = None,
) -> None:
    """Free legacy soft-deleted unique keys inside the caller's transaction."""
    model = {"program": Program, "project": Project, "solution": Solution, "task": Task}[entity]
    name_field = f"{entity}_name"
    query = session.query(model).filter(
        model.space_id == space_ctx.space_id,
        model.deleted_at.is_not(None),
        getattr(model, name_field) == name,
    )
    if entity == "solution":
        query = query.filter(Solution.project_id == parent_id, Solution.version == version)
    elif entity == "task":
        query = query.filter(Task.solution_id == parent_id)
    rows = query.with_for_update().populate_existing().all()
    now = datetime.now(timezone.utc)
    for row in rows:
        entity_id = getattr(row, f"{entity}_id")
        renamed = deleted_work_item_name(name, entity_id, row.deleted_at)
        setattr(row, name_field, renamed)
        row.updated_at = now
        session.add(row)
        log_changes(
            session,
            entity_type=entity,
            entity_id=entity_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes={name_field: (name, renamed)},
        )
    if rows:
        # Flush before inserting/updating the live row so the old key is free.
        session.flush()
