from __future__ import annotations

from typing import Any

from fastapi import status
from sqlalchemy import and_, func
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
        task_id = str(position["task_id"]).strip()
        task_name = str(position["task_name"])
        due_date = str(position["due_date"])
        if not task_id or not task_name or not due_date:
            raise ValueError("cursor fields are empty")
        return (
            int(position["attention"]),
            float(position["urgency"]),
            due_date,
            int(position["priority"]),
            task_name,
            task_id,
        )
    except (KeyError, TypeError, ValueError) as exc:
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
    rows = (
        session.query(Task, Solution, Project, Program)
        .join(Solution, Solution.solution_id == Task.solution_id)
        .join(Project, Project.project_id == Solution.project_id)
        .outerjoin(
            Program,
            and_(
                Program.program_id == Project.program_id,
                Program.space_id == space_ctx.space_id,
            ),
        )
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Task.project_id == Project.project_id)
        .filter(Task.status.notin_(_CLOSED_TASK_STATUSES))
        .filter(func.lower(Task.assignee_user_soeid) == normalized_soeid)
        .all()
    )

    records: list[AgentAssignedWorkItemRead] = []
    for task, solution, project, program in rows:
        task_read = AgentTaskRead.model_validate(
            task_payload(task, solution_repo_url=solution.github_repo_url)
        )
        records.append(
            AgentAssignedWorkItemRead(
                task=task_read,
                program_id=project.program_id,
                program_name=program.program_name if program else None,
                project_name=project.project_name,
                solution_name=solution.solution_name,
                needs_attention=bool(task_read.is_overdue or task.blocked),
            )
        )

    records.sort(key=_sort_key)
    if cursor:
        position = decode_position_cursor(
            cursor,
            scope=ASSIGNED_WORK_CURSOR_SCOPE,
            filters=filters,
        )
        cursor_key = _cursor_sort_key(position)
        records = [record for record in records if _sort_key(record) > cursor_key]

    has_more = len(records) > limit
    page = records[:limit]
    next_cursor = None
    if has_more and page:
        next_cursor = encode_position_cursor(
            scope=ASSIGNED_WORK_CURSOR_SCOPE,
            filters=filters,
            position=_cursor_position(page[-1]),
        )
    return AgentAssignedWorkListRead(
        space_id=space_ctx.space_id,
        assignee_user_soeid=normalized_soeid,
        records=page,
        next_cursor=next_cursor,
        has_more=has_more,
    )
