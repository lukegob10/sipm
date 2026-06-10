from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db
from ...models import ChangeLog, Task, User
from ...schemas import ChangeLogRead, TaskRead
from ...services.smart_cache import cached_call, make_scope_token
from ...services.spaces import SpaceContext
from ...utils.enums import TaskStatus
from .common import (
    _TASKS_DETAIL_TTL_SECONDS,
    _TASKS_LIST_TTL_SECONDS,
    _ensure_solution,
    _get_task,
    _role_scope,
    _solution_repo_map,
    _task_payload,
    _task_query,
)

router = APIRouter()


@router.get(
    "/solutions/{solution_id}/tasks",
    response_model=List[TaskRead],
)
def list_tasks(
    solution_id: str,
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    priority: Optional[int] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    assignee: Optional[str] = None,
    assignee_user_soeid: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    _ensure_solution(session, solution_id, space_ctx)
    status_val = status_filter.value if hasattr(status_filter, "value") else status_filter
    assignee_norm = assignee.strip().lower() if assignee else None
    params = {
        "solution_id": solution_id,
        "status": status_val,
        "priority": priority,
        "due_before": due_before.isoformat() if due_before else None,
        "due_after": due_after.isoformat() if due_after else None,
        "assignee": assignee_norm,
        "assignee_user_soeid": assignee_user_soeid,
    }
    scope_token = make_scope_token("tasks", space_ctx.space_id)

    def _load():
        query = _task_query(session, space_ctx).filter(Task.solution_id == solution_id)
        if status_filter:
            query = query.filter(Task.status == status_filter)
        if priority is not None:
            query = query.filter(Task.priority == priority)
        if due_before:
            query = query.filter(Task.due_date <= due_before)
        if due_after:
            query = query.filter(Task.due_date >= due_after)
        if assignee_norm:
            query = query.filter(func.lower(Task.assignee) == assignee_norm)
        if assignee_user_soeid:
            query = query.filter(Task.assignee_user_soeid == assignee_user_soeid)
        rows = query.order_by(Task.priority.asc(), Task.created_at.asc()).all()
        solution_repo_map = _solution_repo_map(session, space_ctx, [solution_id])
        return [
            _task_payload(row, solution_repo_url=solution_repo_map.get(row.solution_id))
            for row in rows
        ]

    return cached_call(
        endpoint="tasks:list_by_solution",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_TASKS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/tasks", response_model=List[TaskRead])
def list_all_tasks(
    status_filter: Optional[TaskStatus] = Query(None, alias="status"),
    project_id: Optional[str] = None,
    solution_id: Optional[str] = None,
    priority: Optional[int] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    assignee: Optional[str] = None,
    assignee_user_soeid: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    status_val = status_filter.value if hasattr(status_filter, "value") else status_filter
    assignee_norm = assignee.strip().lower() if assignee else None
    params = {
        "status": status_val,
        "project_id": project_id,
        "solution_id": solution_id,
        "priority": priority,
        "due_before": due_before.isoformat() if due_before else None,
        "due_after": due_after.isoformat() if due_after else None,
        "assignee": assignee_norm,
        "assignee_user_soeid": assignee_user_soeid,
    }
    scope_token = make_scope_token("tasks", space_ctx.space_id)

    def _load():
        query = _task_query(session, space_ctx)
        if status_filter:
            query = query.filter(Task.status == status_filter)
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if solution_id:
            query = query.filter(Task.solution_id == solution_id)
        if priority is not None:
            query = query.filter(Task.priority == priority)
        if due_before:
            query = query.filter(Task.due_date <= due_before)
        if due_after:
            query = query.filter(Task.due_date >= due_after)
        if assignee_norm:
            query = query.filter(func.lower(Task.assignee) == assignee_norm)
        if assignee_user_soeid:
            query = query.filter(Task.assignee_user_soeid == assignee_user_soeid)
        rows = query.order_by(Task.priority.asc(), Task.created_at.asc()).all()
        solution_repo_map = _solution_repo_map(
            session, space_ctx, [row.solution_id for row in rows]
        )
        return [
            _task_payload(row, solution_repo_url=solution_repo_map.get(row.solution_id))
            for row in rows
        ]

    return cached_call(
        endpoint="tasks:list_all",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_TASKS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    scope_token = make_scope_token("tasks", space_ctx.space_id)

    def _load():
        task = _get_task(session, task_id, space_ctx)
        solution = _ensure_solution(session, task.solution_id, space_ctx)
        return _task_payload(task, solution_repo_url=solution.github_repo_url)

    return cached_call(
        endpoint="tasks:detail",
        params={"task_id": task_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_TASKS_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/tasks/{task_id}/activity", response_model=List[ChangeLogRead])
def list_task_activity(
    task_id: str,
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    _get_task(session, task_id, space_ctx)
    rows = (
        session.query(ChangeLog)
        .filter(ChangeLog.space_id == space_ctx.space_id)
        .filter(ChangeLog.entity_type == "task")
        .filter(ChangeLog.entity_id == task_id)
        .order_by(ChangeLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return rows
