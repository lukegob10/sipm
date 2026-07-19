from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_non_agent_write, require_space_role
from ...models import Task, User
from ...schemas import TaskBatchUpdate, TaskCreate, TaskRead, TaskUpdate
from ...services.audit_log import log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_str
from ...utils.enums import TaskStatus
from ...services.mutations import commit_refresh_and_publish, commit_session
from .common import (
    _apply_task_completion_state,
    _ensure_solution,
    _get_task,
    _publish_task_mutation,
    _resolve_task_assignee,
    _solution_repo_map,
    _task_payload,
    _task_query,
    normalize_github_repo_url,
)

router = APIRouter()


def _required_task_name(value: object) -> str:
    task_name = normalize_str(value)
    if not task_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_name is required",
        )
    return task_name


@router.post(
    "/solutions/{solution_id}/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    solution_id: str,
    payload: TaskCreate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    solution = _ensure_solution(session, solution_id, space_ctx)
    task_name = _required_task_name(payload.task_name)
    try:
        github_repo_url = normalize_github_repo_url(payload.github_repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    conflict = (
        _task_query(session, space_ctx)
        .filter(Task.solution_id == solution_id)
        .filter(Task.task_name == task_name)
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task name already exists in this solution",
        )

    now = datetime.now(timezone.utc)
    completed_at = now if payload.status == TaskStatus.complete else None
    blocked = payload.blocked or False

    assignee, assignee_user_soeid = _resolve_task_assignee(
        payload.assignee,
        payload.assignee_user_soeid,
        current_user,
    )

    task = Task(
        space_id=space_ctx.space_id,
        project_id=solution.project_id,
        solution_id=solution_id,
        task_name=task_name,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
        completed_at=completed_at,
        assignee=assignee,
        assignee_user_soeid=assignee_user_soeid,
        github_repo_url=github_repo_url,
        estimate_hours=payload.estimate_hours,
        blocked=blocked,
        blocker_note=payload.blocker_note if blocked else None,
        done_criteria=payload.acceptance_criteria,
        capacity_hours=payload.capacity_hours or 0,
        created_at=now,
        updated_at=now,
    )
    session.add(task)
    session.flush()
    log_changes(
        session,
        entity_type="task",
        entity_id=task.task_id,
        user_id=current_user.user_id,
        action="create",
        space_id=space_ctx.space_id,
        changes={
            "task_name": (None, task.task_name),
            "description": (None, task.description),
            "status": (None, task.status),
            "priority": (None, task.priority),
            "due_date": (None, task.due_date),
            "assignee": (None, task.assignee),
            "assignee_user_soeid": (None, task.assignee_user_soeid),
            "github_repo_url": (None, task.github_repo_url),
            "estimate_hours": (None, task.estimate_hours),
            "blocked": (None, task.blocked),
            "blocker_note": (None, task.blocker_note),
            "acceptance_criteria": (None, task.acceptance_criteria),
            "completed_at": (None, task.completed_at),
        },
    )
    commit_refresh_and_publish(
        session,
        task,
        space_id=space_ctx.space_id,
        cache_keys=["tasks"],
        broadcast_channel="tasks",
    )
    return _task_payload(task, solution_repo_url=solution.github_repo_url)


@router.patch("/tasks/{task_id}", response_model=TaskRead)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    task = _get_task(session, task_id, space_ctx)

    update_data = payload.model_dump(exclude_unset=True)
    if "task_name" in update_data:
        update_data["task_name"] = _required_task_name(update_data["task_name"])
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "blocked" in update_data and update_data["blocked"] is None:
        update_data["blocked"] = False
    if update_data.get("blocked") is False:
        update_data["blocker_note"] = None
    if "github_repo_url" in update_data:
        try:
            update_data["github_repo_url"] = normalize_github_repo_url(update_data["github_repo_url"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    fields_to_compare = set(update_data.keys())
    if "status" in update_data:
        fields_to_compare.add("completed_at")
    before = {field: getattr(task, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(task, field, value)

    if "status" in update_data:
        _apply_task_completion_state(
            task,
            next_status=update_data["status"],
            now=datetime.now(timezone.utc),
        )

    task.updated_at = datetime.now(timezone.utc)

    if "task_name" in update_data and update_data["task_name"]:
        conflict = (
            _task_query(session, space_ctx)
            .filter(Task.solution_id == task.solution_id)
            .filter(Task.task_name == update_data["task_name"])
            .filter(Task.task_id != task.task_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task name already exists in this solution",
            )

    session.add(task)
    if update_data:
        log_changes(
            session,
            entity_type="task",
            entity_id=task.task_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes={field: (before.get(field), getattr(task, field)) for field in fields_to_compare},
        )
    commit_refresh_and_publish(
        session,
        task,
        space_id=space_ctx.space_id,
        cache_keys=["tasks"],
        broadcast_channel="tasks",
    )
    solution = _ensure_solution(session, task.solution_id, space_ctx)
    return _task_payload(task, solution_repo_url=solution.github_repo_url)


@router.patch("/tasks/actions/batch", response_model=list[TaskRead])
def batch_update_tasks(
    payload: TaskBatchUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    unique_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in payload.task_ids or []:
        task_id_value = (raw_id or "").strip()
        if not task_id_value or task_id_value in seen:
            continue
        seen.add(task_id_value)
        unique_ids.append(task_id_value)
    if not unique_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="task_ids must include at least one item",
        )
    if payload.due_date is not None and payload.due_date_shift_days is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either due_date or due_date_shift_days, not both",
        )

    rows = (
        _task_query(session, space_ctx)
        .filter(Task.task_id.in_(unique_ids))
        .all()
    )
    rows_by_id = {row.task_id: row for row in rows}
    missing = [task_id_value for task_id_value in unique_ids if task_id_value not in rows_by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tasks not found in current space: {', '.join(missing)}",
        )

    now = datetime.now(timezone.utc)
    updated_rows: list[Task] = []
    for task_id_value in unique_ids:
        row = rows_by_id[task_id_value]
        changes = {}

        def track(field: str, value):
            old = getattr(row, field)
            if old != value:
                setattr(row, field, value)
                changes[field] = (old, value)

        if payload.status is not None:
            track("status", payload.status)
            if payload.status == TaskStatus.complete and not row.completed_at:
                track("completed_at", now)
            elif payload.status != TaskStatus.complete and row.completed_at is not None:
                track("completed_at", None)
        if payload.priority is not None:
            track("priority", payload.priority)
        if payload.blocked is not None:
            track("blocked", payload.blocked)

        if payload.due_date is not None:
            track("due_date", payload.due_date)
        elif payload.due_date_shift_days is not None and row.due_date is not None:
            track("due_date", row.due_date + timedelta(days=payload.due_date_shift_days))

        if payload.clear_assignee:
            track("assignee", "")
            track("assignee_user_soeid", None)
        else:
            if payload.assignee is not None:
                track("assignee", payload.assignee)
            if payload.assignee_user_soeid is not None:
                track("assignee_user_soeid", payload.assignee_user_soeid)

        if not changes:
            updated_rows.append(row)
            continue

        track("updated_at", now)
        session.add(row)
        log_changes(
            session,
            entity_type="task",
            entity_id=row.task_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes=changes,
        )
        updated_rows.append(row)

    commit_session(session)
    for row in updated_rows:
        session.refresh(row)
    _publish_task_mutation(space_ctx.space_id)
    solution_repo_map = _solution_repo_map(
        session,
        space_ctx,
        [row.solution_id for row in updated_rows],
    )
    return [
        _task_payload(row, solution_repo_url=solution_repo_map.get(row.solution_id))
        for row in updated_rows
    ]


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    task = _get_task(session, task_id, space_ctx)
    now = datetime.now(timezone.utc)
    task.deleted_at = now
    task.updated_at = now
    session.add(task)
    log_changes(
        session,
        entity_type="task",
        entity_id=task.task_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    commit_session(session)
    _publish_task_mutation(space_ctx.space_id)
    return None
