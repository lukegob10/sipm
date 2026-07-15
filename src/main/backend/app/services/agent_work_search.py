from __future__ import annotations

from datetime import date, datetime, timezone

from fastapi import status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..models import Program, Project, Solution, Task
from ..schemas.agent import AgentWorkItemListRead, AgentWorkItemSummary
from ..security import security_http_exception
from ..utils import normalize_str
from .agent_pagination import decode_cursor, encode_cursor
from .spaces import SpaceContext

WORK_ITEM_CURSOR_SCOPE = "agent_work_items_v1"
WORK_ITEM_TYPES = {"program", "project", "solution", "task"}
LIFECYCLES = {"active", "archived"}


def _as_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _enum(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value.value if hasattr(value, "value") else value)


def _model_contract(entity_type: str):
    if entity_type == "program":
        return Program, Program.program_id, Program.program_name
    if entity_type == "project":
        return Project, Project.project_id, Project.project_name
    if entity_type == "solution":
        return Solution, Solution.solution_id, Solution.solution_name
    return Task, Task.task_id, Task.task_name


def _summary(entity_type: str, row) -> AgentWorkItemSummary:
    return AgentWorkItemSummary(
        entity_type=entity_type,
        entity_id=getattr(row, f"{entity_type}_id"),
        name=getattr(row, f"{entity_type}_name"),
        program_id=getattr(row, "program_id", None),
        project_id=getattr(row, "project_id", None),
        solution_id=getattr(row, "solution_id", None),
        status=_enum(getattr(row, "status", None)),
        priority=getattr(row, "priority", None),
        due_date=getattr(row, "due_date", None),
        owner_user_soeid=getattr(row, "owner_user_soeid", None),
        assignee_user_soeid=getattr(row, "assignee_user_soeid", None),
        sponsor_user_soeid=getattr(row, "sponsor_user_soeid", None),
        approver_user_soeid=getattr(row, "approver_user_soeid", None),
        lifecycle="archived" if row.deleted_at is not None else "active",
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def search_agent_work_items(
    session: Session,
    space_ctx: SpaceContext,
    *,
    entity_type: str,
    entity_id: str | None = None,
    parent_id: str | None = None,
    exact_name: str | None = None,
    query_text: str | None = None,
    item_status: str | None = None,
    principal_soeid: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    updated_since: datetime | None = None,
    lifecycle: str = "active",
    cursor: str | None = None,
    limit: int = 50,
) -> AgentWorkItemListRead:
    entity_type = normalize_str(entity_type).lower()
    lifecycle = normalize_str(lifecycle).lower() or "active"
    if entity_type not in WORK_ITEM_TYPES:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_ENTITY_TYPE",
            message="entity_type must be program, project, solution, or task",
        )
    if lifecycle not in LIFECYCLES:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_LIFECYCLE",
            message="lifecycle must be active or archived",
        )

    model, id_column, name_column = _model_contract(entity_type)
    normalized_id = normalize_str(entity_id) or None
    normalized_parent = normalize_str(parent_id) or None
    normalized_exact_name = normalize_str(exact_name) or None
    normalized_query = normalize_str(query_text).lower() or None
    normalized_status = normalize_str(item_status).lower() or None
    normalized_principal = normalize_str(principal_soeid).lower() or None
    updated_since_value = _as_naive_utc(updated_since) if updated_since else None
    filters = {
        "space_id": space_ctx.space_id,
        "entity_type": entity_type,
        "entity_id": normalized_id,
        "parent_id": normalized_parent,
        "exact_name": normalized_exact_name,
        "query": normalized_query,
        "status": normalized_status,
        "principal_soeid": normalized_principal,
        "due_from": due_from,
        "due_to": due_to,
        "updated_since": updated_since_value,
        "lifecycle": lifecycle,
    }
    query = session.query(model).filter(model.space_id == space_ctx.space_id)
    query = query.filter(
        model.deleted_at.isnot(None)
        if lifecycle == "archived"
        else model.deleted_at.is_(None)
    )
    if lifecycle == "active" and entity_type == "solution":
        query = query.join(Project, Project.project_id == Solution.project_id).filter(
            Project.deleted_at.is_(None),
            Project.space_id == space_ctx.space_id,
        )
    if lifecycle == "active" and entity_type == "task":
        query = (
            query.join(Solution, Solution.solution_id == Task.solution_id)
            .join(Project, Project.project_id == Solution.project_id)
            .filter(
                Solution.deleted_at.is_(None),
                Solution.space_id == space_ctx.space_id,
                Project.deleted_at.is_(None),
                Project.space_id == space_ctx.space_id,
            )
        )
    if normalized_id:
        query = query.filter(id_column == normalized_id)
    if normalized_parent:
        parent_column = {
            "project": Project.program_id,
            "solution": Solution.project_id,
            "task": Task.solution_id,
        }.get(entity_type)
        if parent_column is None:
            raise security_http_exception(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="UNSUPPORTED_FILTER",
                message="parent_id is not supported for programs",
            )
        query = query.filter(parent_column == normalized_parent)
    if normalized_exact_name:
        query = query.filter(name_column == normalized_exact_name)
    if normalized_query:
        query = query.filter(func.lower(name_column).like(f"%{normalized_query}%"))
    status_column = getattr(model, "status", None)
    if normalized_status:
        if status_column is None:
            raise security_http_exception(
                status_code=400,
                code="UNSUPPORTED_FILTER",
                message="status is not supported for programs",
            )
        query = query.filter(status_column == normalized_status)
    due_column = getattr(model, "due_date", None)
    if due_from or due_to:
        if due_column is None:
            raise security_http_exception(
                status_code=400,
                code="UNSUPPORTED_FILTER",
                message="due-date filters are not supported for this entity type",
            )
        if due_from:
            query = query.filter(due_column >= due_from)
        if due_to:
            query = query.filter(due_column <= due_to)
    if normalized_principal:
        principal_columns = [
            column
            for column in (
                getattr(model, "owner_user_soeid", None),
                getattr(model, "assignee_user_soeid", None),
                getattr(model, "sponsor_user_soeid", None),
                getattr(model, "approver_user_soeid", None),
            )
            if column is not None
        ]
        if not principal_columns:
            raise security_http_exception(
                status_code=400,
                code="UNSUPPORTED_FILTER",
                message="principal_soeid is not supported for programs",
            )
        query = query.filter(
            or_(
                *[
                    func.lower(column) == normalized_principal
                    for column in principal_columns
                ]
            )
        )
    if updated_since_value:
        query = query.filter(model.updated_at >= updated_since_value)
    if cursor:
        cursor_at, cursor_id = decode_cursor(
            cursor, scope=WORK_ITEM_CURSOR_SCOPE, filters=filters
        )
        cursor_at = _as_naive_utc(cursor_at)
        query = query.filter(
            or_(
                model.updated_at < cursor_at,
                and_(model.updated_at == cursor_at, id_column < cursor_id),
            )
        )

    rows = (
        query.order_by(model.updated_at.desc(), id_column.desc()).limit(limit + 1).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        next_cursor = encode_cursor(
            scope=WORK_ITEM_CURSOR_SCOPE,
            filters=filters,
            ordered_at=rows[-1].updated_at,
            ordered_id=getattr(rows[-1], f"{entity_type}_id"),
        )
    return AgentWorkItemListRead(
        space_id=space_ctx.space_id,
        entity_type=entity_type,
        records=[_summary(entity_type, row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
