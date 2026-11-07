from __future__ import annotations

from datetime import date, datetime, timezone
from heapq import nsmallest
from math import isfinite
from typing import Any

from fastapi import status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Program, Project, Solution, Task
from ..schemas.agent import (
    AgentAssignedWorkItemRead,
    AgentAssignedWorkListRead,
    AgentTaskRead,
)
from ..security import security_http_exception
from ..utils import normalize_str
from ..utils.enums import TaskStatus
from .agent_pagination import decode_position_cursor, encode_position_cursor
from .spaces import SpaceContext
from .work_items import task_payload


ASSIGNED_WORK_CURSOR_SCOPE = "agent_assigned_work_v1"
_CLOSED_TASK_STATUSES = (TaskStatus.complete, TaskStatus.abandoned)


def _sort_key(item: AgentAssignedWorkItemRead) -> tuple[int, float, str, int, str, str]:
    task = item.task
    return (
        0 if item.needs_attention else 1,
        -float(task.urgency_score),
        task.due_date.isoformat() if task.due_date else "9999-12-31",
        int(task.priority),
        task.task_name.casefold(),
        task.task_id,
    )


def _cursor_position(item: AgentAssignedWorkItemRead) -> dict[str, Any]:
    attention, urgency, due_date, priority, task_name, task_id = _sort_key(item)
    return {
        "attention": attention,
        "urgency": urgency,
        "due_date": due_date,
        "priority": priority,
        "task_name": task_name,
        "task_id": task_id,
    }


def _cursor_sort_key(position: dict[str, Any]) -> tuple[int, float, str, int, str, str]:
    try:
        task_id = position["task_id"]
        task_name = position["task_name"]
        due_date = str(position["due_date"])
        if not isinstance(task_id, str) or not task_id.strip() or not isinstance(task_name, str) or not due_date:
            raise ValueError("cursor fields are invalid")
        urgency = float(position["urgency"])
        if not isfinite(urgency):
            raise ValueError("cursor urgency is invalid")
        task_id = task_id.strip()
        return (
            int(position["attention"]),
            urgency,
            due_date,
            int(position["priority"]),
            task_name,
            task_id,
        )
    except (KeyError, OverflowError, TypeError, ValueError) as exc:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_CURSOR",
            message="Cursor is invalid for this request",
        ) from exc


def list_agent_assigned_work(
    session: Session,
    space_ctx: SpaceContext,
    *,
    assignee_user_soeid: str,
    cursor: str | None,
    limit: int,
) -> AgentAssignedWorkListRead:
    normalized_soeid = normalize_str(assignee_user_soeid).lower()
    if not normalized_soeid:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_ASSIGNEE",
            message="assignee_user_soeid is required",
        )

    filters = {
        "space_id": space_ctx.space_id,
        "assignee_user_soeid": normalized_soeid,
    }
    position = None
    as_of = datetime.now(timezone.utc).date()
    if cursor:
        position = decode_position_cursor(
            cursor,
            scope=ASSIGNED_WORK_CURSOR_SCOPE,
            filters=filters,
        )
        if "as_of" in position:
            try:
                as_of = date.fromisoformat(position["as_of"])
            except (TypeError, ValueError) as exc:
                raise security_http_exception(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="INVALID_CURSOR",
                    message="Cursor is invalid for this request",
                ) from exc
    rows = (
        session.query(
            Task,
            Solution.github_repo_url,
            Solution.solution_name,
            Project.project_name,
            Program.program_id,
            Program.program_name,
        )
        .join(Solution, Solution.solution_id == Task.solution_id)
        .join(Project, Project.project_id == Solution.project_id)
        .join(Program, Program.program_id == Project.program_id)
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.deleted_at.is_(None))
        .filter(Task.project_id == Project.project_id)
        .filter(Task.status.notin_(_CLOSED_TASK_STATUSES))
        .filter(func.lower(func.trim(Task.assignee_user_soeid)) == normalized_soeid)
        .yield_per(250)
    )

    cursor_key = _cursor_sort_key(position) if position is not None else None

    def candidates():
        for task, repo_url, solution_name, project_name, program_id, program_name in rows:
            task_read = AgentTaskRead.model_validate(
                task_payload(task, solution_repo_url=repo_url, actionability_date=as_of)
            )
            item = AgentAssignedWorkItemRead(
                task=task_read,
                program_id=program_id,
                program_name=program_name,
                project_name=project_name,
                solution_name=solution_name,
                needs_attention=bool(task_read.is_overdue or task.blocked),
            )
            if cursor_key is None or _sort_key(item) > cursor_key:
                yield item

    # Urgency is computed in Python, so all candidates must be inspected, but
    # only a page and one look-ahead item need to be retained for sorting.
    records = nsmallest(limit + 1, candidates(), key=_sort_key)
    has_more = len(records) > limit
    page = records[:limit]
    next_cursor = None
    if has_more and page:
        next_cursor = encode_position_cursor(
            scope=ASSIGNED_WORK_CURSOR_SCOPE,
            filters=filters,
            position={**_cursor_position(page[-1]), "as_of": as_of.isoformat()},
        )
    return AgentAssignedWorkListRead(
        space_id=space_ctx.space_id,
        assignee_user_soeid=normalized_soeid,
        records=page,
        next_cursor=next_cursor,
        has_more=has_more,
    )
