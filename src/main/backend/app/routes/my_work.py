from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, false, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import current_space as current_space_dep
from ..deps import get_db, require_interactive_user
from ..models import Program, Project, Solution, Task, User, UserPreference, UserTaskState
from ..schemas import (
    MyWorkItemRead,
    RepositoryInventoryItemRead,
    UserPreferenceRead,
    UserPreferenceUpdate,
    UserTaskStateRead,
    UserTaskStateUpdate,
)
from ..services.spaces import SpaceContext
from ..services.github_repo_urls import normalize_github_repo_url
from ..services.work_items import task_payload

router = APIRouter()


def _in_batches(column, values):
    ids = list(values)
    if not ids:
        return false()
    return or_(*(column.in_(ids[index:index + 500]) for index in range(0, len(ids), 500)))


def _preference_payload(preference: UserPreference | None) -> UserPreferenceRead:
    if preference is None:
        return UserPreferenceRead()
    return UserPreferenceRead(
        developer_mode_enabled=bool(preference.developer_mode_enabled),
        theme=preference.theme or "dark",
        has_saved_preferences=True,
    )


def _assigned_to_user(user: User):
    soeid = str(user.soeid or "").strip().lower()
    return func.lower(func.trim(Task.assignee_user_soeid)) == soeid


def _repository_name(url: str) -> str:
    github_prefix = "https://github.com/"
    return url[len(github_prefix) :] if url.startswith(github_prefix) else url


def _utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utc_naive(value: datetime | None) -> datetime | None:
    aware = _utc_aware(value)
    return aware.replace(tzinfo=None) if aware is not None else None


def _private_state_payload(task_id: str, private_state: UserTaskState | None) -> UserTaskStateRead:
    if private_state is None:
        return UserTaskStateRead(task_id=task_id)
    return UserTaskStateRead(
        task_id=private_state.task_id,
        bucket=private_state.bucket or "later",
        sort_rank=private_state.sort_rank,
        reminder_at=_utc_aware(private_state.reminder_at),
        private_note=private_state.private_note,
    )


def _eligible_task_query(session: Session, space_ctx: SpaceContext, user: User):
    return (
        session.query(Task)
        .join(Solution, Solution.solution_id == Task.solution_id)
        .join(Project, Project.project_id == Solution.project_id)
        .join(Program, Program.program_id == Project.program_id)
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.deleted_at.is_(None))
        .filter(Task.project_id == Solution.project_id)
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.deleted_at.is_(None))
        .filter(_assigned_to_user(user))
    )


@router.get("/users/me/preferences", response_model=UserPreferenceRead)
def get_my_preferences(
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
) -> UserPreferenceRead:
    preference = session.get(UserPreference, current_user.user_id)
    return _preference_payload(preference)


@router.patch("/users/me/preferences", response_model=UserPreferenceRead)
def update_my_preferences(
    payload: UserPreferenceUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
) -> UserPreferenceRead:
    preference = session.get(UserPreference, current_user.user_id)
    created = preference is None
    if created:
        preference = UserPreference(user_id=current_user.user_id)

    def apply_changes(target: UserPreference) -> None:
        if payload.developer_mode_enabled is not None:
            target.developer_mode_enabled = bool(payload.developer_mode_enabled)
        if payload.theme is not None:
            target.theme = payload.theme
        session.add(target)

    apply_changes(preference)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if not created:
            raise
        winner = session.get(UserPreference, current_user.user_id)
        if winner is None:
            raise
        preference = winner
        apply_changes(preference)
        session.commit()
    session.refresh(preference)
    return _preference_payload(preference)


@router.get("/my-work", response_model=list[MyWorkItemRead])
def list_my_work(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(require_interactive_user),
) -> list[MyWorkItemRead]:
    rows = (
        _eligible_task_query(session, space_ctx, current_user)
        .outerjoin(
            UserTaskState,
            and_(
                UserTaskState.task_id == Task.task_id,
                UserTaskState.user_id == current_user.user_id,
                UserTaskState.space_id == space_ctx.space_id,
            ),
        )
        .with_entities(
            Task,
            UserTaskState,
            Solution.github_repo_url,
            Solution.solution_name,
            Project.program_id,
            Project.project_name,
            Program.program_name,
        )
        .all()
    )
    if not rows:
        return []
    now = datetime.now(timezone.utc)

    result: list[MyWorkItemRead] = []
    for task, private_state, solution_repo_url, solution_name, program_id, project_name, program_name in rows:
        payload = task_payload(task, solution_repo_url=solution_repo_url)
        private_reminder_at = _utc_aware(private_state.reminder_at) if private_state else None
        reminder_due = bool(private_reminder_at and private_reminder_at <= now)
        status_value = getattr(task.status, "value", str(task.status)).lower()
        is_closed = status_value in {"complete", "abandoned"}
        needs_attention = bool(
            not is_closed and (payload["is_overdue"] or task.blocked or reminder_due)
        )
        result.append(
            MyWorkItemRead(
                task=payload,
                program_id=program_id,
                program_name=program_name,
                project_name=project_name,
                solution_name=solution_name,
                private_bucket=(private_state.bucket or "later") if private_state else "later",
                private_sort_rank=private_state.sort_rank if private_state else 0,
                private_reminder_at=private_reminder_at,
                private_note=private_state.private_note if private_state else None,
                reminder_due=reminder_due,
                needs_attention=needs_attention,
            )
        )

    result.sort(
        key=lambda item: (
            0 if item.needs_attention else 1,
            item.private_sort_rank,
            -item.task.urgency_score,
            item.task.due_date.isoformat() if item.task.due_date else "9999-12-31",
            item.task.priority,
            item.task.task_name.lower(),
        )
    )
    return result


@router.get("/repository-inventory", response_model=list[RepositoryInventoryItemRead])
def list_repository_inventory(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _current_user: User = Depends(require_interactive_user),
) -> list[RepositoryInventoryItemRead]:
    rows = (
        session.query(Solution, Project.project_name, Program.program_name)
        .select_from(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .join(Program, Program.program_id == Project.program_id)
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.deleted_at.is_(None))
        .all()
    )
    if not rows:
        return []

    solution_by_id = {
        solution.solution_id: (solution, project_name, program_name)
        for solution, project_name, program_name in rows
    }
    tasks = (
        session.query(Task)
        .join(Solution, Solution.solution_id == Task.solution_id)
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.deleted_at.is_(None))
        .filter(Task.project_id == Solution.project_id)
        .filter(_in_batches(Task.solution_id, solution_by_id))
        .all()
    )

    inventory: dict[str, dict] = {}

    def ensure_repo(url: str) -> dict:
        try:
            canonical = normalize_github_repo_url(url, validate_length=False)
        except ValueError:
            canonical = None
        # Only group canonical GitHub URLs. Preserve distinct legacy values
        # that do not follow the URL contract.
        key = f"github:{url.lower()}" if canonical == url else f"legacy:{url}"
        if key not in inventory:
            inventory[key] = {
                "github_repo_url": url,
                "repository_name": _repository_name(url),
                "program_names": set(),
                "project_names": set(),
                "solution_names": set(),
                "solution_ids": set(),
                "task_ids": set(),
                "solution_attachment_ids": set(),
                "task_override_ids": set(),
                "last_updated_at": None,
            }
        entry = inventory[key]
        if url < entry["github_repo_url"]:
            entry["github_repo_url"] = url
            entry["repository_name"] = _repository_name(url)
        return entry

    def add_context(entry: dict, solution: Solution) -> None:
        _, project_name, program_name = solution_by_id[solution.solution_id]
        entry["solution_ids"].add(solution.solution_id)
        entry["solution_names"].add(solution.solution_name)
        entry["project_names"].add(project_name)
        entry["program_names"].add(program_name)

    for solution, _, _ in rows:
        if not solution.github_repo_url:
            continue
        entry = ensure_repo(solution.github_repo_url)
        add_context(entry, solution)
        entry["solution_attachment_ids"].add(solution.solution_id)
        entry["last_updated_at"] = max(
            filter(None, [entry["last_updated_at"], solution.updated_at]),
            default=None,
        )

    for task in tasks:
        solution, _, _ = solution_by_id[task.solution_id]
        effective_url = task.github_repo_url or solution.github_repo_url
        if not effective_url:
            continue
        entry = ensure_repo(effective_url)
        add_context(entry, solution)
        entry["task_ids"].add(task.task_id)
        if task.github_repo_url:
            entry["task_override_ids"].add(task.task_id)
        entry["last_updated_at"] = max(
            filter(None, [entry["last_updated_at"], task.updated_at]),
            default=None,
        )

    result = [
        RepositoryInventoryItemRead(
            github_repo_url=entry["github_repo_url"],
            repository_name=entry["repository_name"],
            program_names=sorted(entry["program_names"], key=str.lower),
            project_names=sorted(entry["project_names"], key=str.lower),
            solution_names=sorted(entry["solution_names"], key=str.lower),
            solution_count=len(entry["solution_ids"]),
            task_count=len(entry["task_ids"]),
            solution_attachment_count=len(entry["solution_attachment_ids"]),
            task_override_count=len(entry["task_override_ids"]),
            last_updated_at=entry["last_updated_at"],
        )
        for entry in inventory.values()
    ]
    result.sort(key=lambda item: item.repository_name.lower())
    return result


@router.patch("/my-work/tasks/{task_id}/state", response_model=UserTaskStateRead)
def update_my_work_state(
    task_id: str,
    payload: UserTaskStateUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(require_interactive_user),
) -> UserTaskStateRead:
    task = _eligible_task_query(session, space_ctx, current_user).filter(Task.task_id == task_id).first()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task is not eligible for My Work")
    private_state = (
        session.query(UserTaskState)
        .filter(UserTaskState.user_id == current_user.user_id)
        .filter(UserTaskState.space_id == space_ctx.space_id)
        .filter(UserTaskState.task_id == task_id)
        .first()
    )
    fields = payload.model_fields_set
    if not fields:
        return _private_state_payload(task_id, private_state)
    created = private_state is None
    if created:
        private_state = UserTaskState(
            user_id=current_user.user_id,
            space_id=space_ctx.space_id,
            task_id=task_id,
        )

    def apply_changes(state: UserTaskState) -> None:
        for field in fields:
            value = getattr(payload, field)
            setattr(state, field, _utc_naive(value) if field == "reminder_at" else value)
        session.add(state)

    apply_changes(private_state)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        if not created:
            raise
        winner = (
            session.query(UserTaskState)
            .filter(UserTaskState.user_id == current_user.user_id)
            .filter(UserTaskState.space_id == space_ctx.space_id)
            .filter(UserTaskState.task_id == task_id)
            .first()
        )
        if winner is None:
            raise
        task = _eligible_task_query(session, space_ctx, current_user).filter(Task.task_id == task_id).first()
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task is not eligible for My Work")
        private_state = winner
        apply_changes(private_state)
        session.commit()
    session.refresh(private_state)
    return _private_state_payload(task_id, private_state)


@router.delete("/my-work/tasks/{task_id}/state", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_work_state(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(require_interactive_user),
) -> None:
    private_state = (
        session.query(UserTaskState)
        .filter(UserTaskState.user_id == current_user.user_id)
        .filter(UserTaskState.space_id == space_ctx.space_id)
        .filter(UserTaskState.task_id == task_id)
        .first()
    )
    if private_state is not None:
        session.delete(private_state)
        session.commit()
