from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
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
from ..services.work_items import task_payload

router = APIRouter()


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


def _eligible_task_query(session: Session, space_ctx: SpaceContext, user: User):
    return (
        session.query(Task)
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.deleted_at.is_(None))
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
    if preference is None:
        preference = UserPreference(user_id=current_user.user_id)
    if payload.developer_mode_enabled is not None:
        preference.developer_mode_enabled = bool(payload.developer_mode_enabled)
    if payload.theme is not None:
        preference.theme = payload.theme
    session.add(preference)
    session.commit()
    session.refresh(preference)
    return _preference_payload(preference)


@router.get("/my-work", response_model=list[MyWorkItemRead])
def list_my_work(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(require_interactive_user),
) -> list[MyWorkItemRead]:
    rows = _eligible_task_query(session, space_ctx, current_user).all()
    if not rows:
        return []

    task_ids = [task.task_id for task in rows]
    state_rows = (
        session.query(UserTaskState)
        .filter(UserTaskState.user_id == current_user.user_id)
        .filter(UserTaskState.space_id == space_ctx.space_id)
        .filter(UserTaskState.task_id.in_(task_ids))
        .all()
    )
    state_by_task_id = {row.task_id: row for row in state_rows}

    solution_ids = {task.solution_id for task in rows}
    project_ids = {task.project_id for task in rows}
    solutions = (
        session.query(Solution)
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.solution_id.in_(solution_ids))
        .all()
    )
    projects = (
        session.query(Project)
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.project_id.in_(project_ids))
        .all()
    )
    project_by_id = {row.project_id: row for row in projects}
    solution_by_id = {row.solution_id: row for row in solutions}
    program_ids = {project.program_id for project in projects}
    programs = (
        session.query(Program)
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.program_id.in_(program_ids))
        .all()
        if program_ids
        else []
    )
    program_by_id = {row.program_id: row for row in programs}

    result: list[MyWorkItemRead] = []
    for task in rows:
        solution = solution_by_id[task.solution_id]
        project = project_by_id[task.project_id]
        program = program_by_id.get(project.program_id)
        private_state = state_by_task_id.get(task.task_id)
        payload = task_payload(task, solution_repo_url=solution.github_repo_url)
        needs_attention = bool(payload["is_overdue"] or task.blocked)
        result.append(
            MyWorkItemRead(
                task=payload,
                program_id=project.program_id,
                program_name=program.program_name if program else None,
                project_name=project.project_name,
                solution_name=solution.solution_name,
                private_sort_rank=private_state.sort_rank if private_state else 0,
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
    solutions = (
        session.query(Solution)
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.deleted_at.is_(None))
        .all()
    )
    if not solutions:
        return []

    solution_by_id = {row.solution_id: row for row in solutions}
    project_ids = {row.project_id for row in solutions}
    projects = (
        session.query(Project)
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.project_id.in_(project_ids))
        .all()
    )
    project_by_id = {row.project_id: row for row in projects}
    program_ids = {row.program_id for row in projects if row.program_id}
    programs = (
        session.query(Program)
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.program_id.in_(program_ids))
        .all()
        if program_ids
        else []
    )
    program_by_id = {row.program_id: row for row in programs}
    tasks = (
        session.query(Task)
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.deleted_at.is_(None))
        .filter(Task.solution_id.in_(solution_by_id))
        .all()
    )

    inventory: dict[str, dict] = {}

    def ensure_repo(url: str) -> dict:
        if url not in inventory:
            inventory[url] = {
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
        return inventory[url]

    def add_context(entry: dict, solution: Solution) -> None:
        project = project_by_id.get(solution.project_id)
        program = program_by_id.get(project.program_id) if project else None
        entry["solution_ids"].add(solution.solution_id)
        entry["solution_names"].add(solution.solution_name)
        if project:
            entry["project_names"].add(project.project_name)
        if program:
            entry["program_names"].add(program.program_name)

    for solution in solutions:
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
        solution = solution_by_id.get(task.solution_id)
        if solution is None:
            continue
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
        .filter(UserTaskState.task_id == task_id)
        .first()
    )
    if private_state is None:
        private_state = UserTaskState(
            user_id=current_user.user_id,
            space_id=space_ctx.space_id,
            task_id=task_id,
        )
    private_state.sort_rank = payload.sort_rank
    session.add(private_state)
    session.commit()
    session.refresh(private_state)
    return UserTaskStateRead(
        task_id=private_state.task_id,
        sort_rank=private_state.sort_rank,
    )


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
