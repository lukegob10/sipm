from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models import Project, Solution, Task
from ...schemas import TaskRead
from ...services.github_repo_urls import normalize_github_repo_url, resolve_effective_github_repo_url
from ...services.mutations import publish_space_mutation
from ...services.spaces import SpaceContext
from ...utils import enable_all_phases, normalize_str
from ...utils.enums import TaskStatus

_TASKS_LIST_TTL_SECONDS = 20
_TASKS_DETAIL_TTL_SECONDS = 30
_DUE_SOON_DAYS = 14
_STALE_DAYS = 7
_DONE_STATUSES = {TaskStatus.complete, TaskStatus.abandoned}


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _is_done_status(status_value: TaskStatus | str | None) -> bool:
    if status_value is None:
        return False
    if status_value in _DONE_STATUSES:
        return True
    raw = status_value.value if hasattr(status_value, "value") else str(status_value)
    return raw in {TaskStatus.complete.value, TaskStatus.abandoned.value}


def _task_actionability(task: Task) -> dict:
    today = datetime.now(timezone.utc).date()
    is_done = _is_done_status(task.status)
    due_date = task.due_date
    updated_date = task.updated_at.date() if task.updated_at else today

    is_overdue = bool(due_date and due_date < today and not is_done)
    is_due_soon = bool(
        due_date and not is_done and 0 <= (due_date - today).days <= _DUE_SOON_DAYS
    )
    is_stale = bool(not is_done and (today - updated_date).days > _STALE_DAYS)

    urgency_score = 0.0
    if not is_done:
        priority = max(1, min(5, int(task.priority or 3)))
        priority_score = (6 - priority) * 15

        due_score = 0
        if due_date:
            days_to_due = (due_date - today).days
            if days_to_due < 0:
                due_score = 45
            elif days_to_due <= _DUE_SOON_DAYS:
                due_score = max(8, (_DUE_SOON_DAYS - days_to_due + 1) * 2)

        blocked_score = 18 if task.blocked else 0
        stale_score = 10 if is_stale else 0
        urgency_score = float(min(100, priority_score + due_score + blocked_score + stale_score))

    return {
        "is_overdue": is_overdue,
        "is_due_soon": is_due_soon,
        "is_stale": is_stale,
        "urgency_score": round(urgency_score, 2),
    }


def _task_payload(
    task: Task,
    *,
    solution_repo_url: Optional[str] = None,
) -> dict:
    payload = TaskRead.model_validate(task).model_dump(mode="json")
    effective_repo_url, repo_source = resolve_effective_github_repo_url(
        solution_repo_url=solution_repo_url,
        task_repo_url=task.github_repo_url,
    )
    payload["effective_github_repo_url"] = effective_repo_url
    payload["repo_source"] = repo_source
    payload.update(_task_actionability(task))
    return payload


def _apply_task_completion_state(
    task: Task,
    *,
    next_status: TaskStatus,
    now: datetime,
) -> None:
    if next_status == TaskStatus.complete:
        task.completed_at = task.completed_at or now
        return
    task.completed_at = None


def _resolve_task_assignee(
    assignee_value: object | None,
    assignee_user_soeid_value: object | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    assignee = normalize_str(assignee_value) or display_name or current_soeid or ""
    assignee_user_soeid = normalize_str(assignee_user_soeid_value) or None
    if assignee_user_soeid is None and current_soeid and assignee in {display_name, current_soeid}:
        assignee_user_soeid = current_soeid
    return assignee, assignee_user_soeid


def _publish_task_mutation(space_id: str) -> None:
    publish_space_mutation(
        space_id,
        ["tasks"],
        broadcast_channel="tasks",
    )


def _publish_task_import(
    space_id: str,
    *,
    projects_created: int,
    solutions_created: int,
) -> None:
    if projects_created > 0:
        publish_space_mutation(
            space_id,
            ["projects"],
            broadcast_channel="projects",
        )
    if solutions_created > 0:
        publish_space_mutation(
            space_id,
            ["solutions"],
            broadcast_channel="solutions",
        )
    _publish_task_mutation(space_id)


def _solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _task_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Task)
        .join(Solution, Solution.solution_id == Task.solution_id)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Task.deleted_at.is_(None))
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _solution_repo_map(session: Session, space_ctx: SpaceContext, solution_ids: list[str]) -> dict[str, Optional[str]]:
    valid_ids = [solution_id for solution_id in solution_ids if solution_id]
    if not valid_ids:
        return {}
    rows = (
        _solution_query(session, space_ctx)
        .filter(Solution.solution_id.in_(valid_ids))
        .all()
    )
    return {row.solution_id: row.github_repo_url for row in rows}


def _ensure_solution(session: Session, solution_id: str, space_ctx: SpaceContext) -> Solution:
    solution = (
        _solution_query(session, space_ctx)
        .filter(Solution.solution_id == solution_id)
        .first()
    )
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
    return solution


def _get_task(session: Session, task_id: str, space_ctx: SpaceContext) -> Task:
    task = (
        _task_query(session, space_ctx)
        .filter(Task.task_id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


def _run_enable_all_phases(session: Session, solution_id: str) -> None:
    from . import enable_all_phases as enable_all_phases_hook

    enable_all_phases_hook(session, solution_id)


__all__ = [
    "_TASKS_DETAIL_TTL_SECONDS",
    "_TASKS_LIST_TTL_SECONDS",
    "_apply_task_completion_state",
    "_ensure_solution",
    "_get_task",
    "_project_query",
    "_publish_task_import",
    "_publish_task_mutation",
    "_resolve_task_assignee",
    "_role_scope",
    "_run_enable_all_phases",
    "_solution_query",
    "_solution_repo_map",
    "_task_payload",
    "_task_query",
    "enable_all_phases",
    "normalize_github_repo_url",
]
