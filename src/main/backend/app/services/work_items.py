from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Phase, Program, Project, Solution, SolutionPhase, Task
from ..schemas import ProjectRead, SolutionRead, TaskRead
from ..utils import enable_all_phases, normalize_str
from ..utils.enums import RagStatus, TaskStatus
from .github_repo_urls import resolve_effective_github_repo_url
from .mutations import publish_space_mutation
from .programs import ensure_default_program
from .realtime import schedule_broadcast
from .smart_cache import invalidate_space
from .spaces import SpaceContext

PROJECTS_LIST_TTL_SECONDS = 20
PROJECTS_DETAIL_TTL_SECONDS = 30
SOLUTIONS_LIST_TTL_SECONDS = 20
SOLUTIONS_DETAIL_TTL_SECONDS = 30
TASKS_LIST_TTL_SECONDS = 20
TASKS_DETAIL_TTL_SECONDS = 30
PROJECT_CREATE_AUDIT_FIELDS = (
    "program_id",
    "project_name",
    "status",
    "description",
    "success_criteria",
    "sponsor",
    "sponsor_user_soeid",
    "owner",
    "owner_user_soeid",
    "strategic_objective",
    "priority",
)
DUE_SOON_DAYS = 14
STALE_DAYS = 7
DONE_STATUSES = {TaskStatus.complete, TaskStatus.abandoned}


def role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def project_payload(project: Project, *, program_name: str | None = None) -> dict:
    data = ProjectRead.model_validate(project).model_dump(mode="json")
    data["program_name"] = program_name
    return data


def project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def active_project_name_conflict_query(session: Session, *, project_name: str, space_id: str):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_id)
        .filter(Project.project_name == project_name)
    )


def ensure_program_exists(session: Session, program_id: str, space_ctx: SpaceContext) -> Program:
    program = (
        session.query(Program)
        .filter(Program.program_id == program_id)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .first()
    )
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


def default_program(session: Session, space_ctx: SpaceContext) -> Program:
    return ensure_default_program(session, space_ctx)


def get_project_or_404(session: Session, project_id: str, space_ctx: SpaceContext) -> Project:
    project = (
        session.query(Project)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def is_project_name_conflict_integrity_error(exc: IntegrityError) -> bool:
    parts = [
        str(exc),
        str(getattr(exc, "orig", "")),
        str(getattr(exc, "statement", "")),
    ]
    text = " ".join(parts).lower()
    if "uix_project_space_name" in text or "uix_project_name" in text:
        return True
    has_unique_marker = any(
        marker in text
        for marker in (
            "ora-03301",
            "ora-00001",
            "unique constraint",
            "unique constraint failed",
        )
    )
    if not has_unique_marker:
        return False
    return ("project_name" in text) or ("tb_ta_pm_projects" in text)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def deleted_project_name(project_name: str, project_id: str, deleted_at: datetime) -> str:
    base = (project_name or "Project").strip() or "Project"
    stamp = as_utc(deleted_at).strftime("%Y%m%dT%H%M%SZ")
    token = (project_id or "")[:8] or "deleted"
    suffix = f" [deleted {stamp} {token}]"
    max_base_len = max(1, 255 - len(suffix))
    return f"{base[:max_base_len]}{suffix}"


def resolve_project_sponsor(
    sponsor_value: object | None,
    sponsor_user_soeid_value: object | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    sponsor = normalize_str(sponsor_value) or display_name or current_soeid or "Sponsor"
    sponsor_user_soeid = normalize_str(sponsor_user_soeid_value) or None
    if sponsor_user_soeid is None and current_soeid and sponsor in {display_name, current_soeid}:
        sponsor_user_soeid = current_soeid
    return sponsor, sponsor_user_soeid


def resolve_project_owner(
    owner_value: object | None,
    owner_user_soeid_value: object | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    owner = normalize_str(owner_value) or display_name or current_soeid or ""
    owner_user_soeid = normalize_str(owner_user_soeid_value) or None
    if owner_user_soeid is None and current_soeid and owner in {display_name, current_soeid}:
        owner_user_soeid = current_soeid
    return owner, owner_user_soeid


def project_create_changes(project: Project) -> dict[str, tuple[object | None, object | None]]:
    return {field: (None, getattr(project, field)) for field in PROJECT_CREATE_AUDIT_FIELDS}


def project_change_set(
    project: Project,
    before: dict[str, object | None],
    fields: Iterable[str],
) -> dict[str, tuple[object | None, object | None]]:
    return {field: (before.get(field), getattr(project, field)) for field in fields}


def publish_project_mutation(space_id: str) -> None:
    invalidate_space(space_id, ["projects"])
    schedule_broadcast("projects", space_id=space_id)


def publish_project_deletion(space_id: str) -> None:
    invalidate_space(space_id, ["projects", "solutions", "tasks"])
    schedule_broadcast("projects", space_id=space_id)
    schedule_broadcast("solutions", space_id=space_id)
    schedule_broadcast("tasks", space_id=space_id)


def solution_payload(solution: Solution) -> dict:
    return SolutionRead.model_validate(solution).model_dump(mode="json")


def publish_solution_mutation(
    space_id: str,
    *,
    invalidate_tasks: bool = False,
) -> None:
    cache_keys = ["solutions"]
    if invalidate_tasks:
        cache_keys.append("tasks")
    publish_space_mutation(
        space_id,
        cache_keys,
        broadcast_channel="solutions",
    )
    if invalidate_tasks:
        publish_space_mutation(
            space_id,
            ["tasks"],
            broadcast_channel="tasks",
        )


def publish_solution_deletion(space_id: str) -> None:
    publish_solution_mutation(
        space_id,
        invalidate_tasks=True,
    )


def publish_solution_import(
    space_id: str,
    *,
    projects_created: int,
    invalidate_tasks: bool = False,
) -> None:
    if projects_created > 0:
        publish_space_mutation(
            space_id,
            ["projects"],
            broadcast_channel="projects",
        )
    publish_solution_mutation(
        space_id,
        invalidate_tasks=invalidate_tasks,
    )


def parse_rag_status(raw: Optional[str]) -> Optional[RagStatus]:
    value = normalize_str(raw).lower()
    if not value:
        return None
    for candidate in RagStatus:
        if candidate.value == value:
            return candidate
    raise ValueError(f"invalid rag_status '{raw}', expected one of: red, amber, green")


def resolve_solution_owner(
    owner_value: object | None,
    owner_user_soeid_value: object | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    owner = normalize_str(owner_value) or display_name or current_soeid or ""
    owner_user_soeid = normalize_str(owner_user_soeid_value) or None
    if owner_user_soeid is None and current_soeid and owner in {display_name, current_soeid}:
        owner_user_soeid = current_soeid
    return owner, owner_user_soeid


def resolve_solution_assignee(
    assignee_value: object | None,
    assignee_user_soeid_value: object | None,
    *,
    owner: str,
    owner_user_soeid: str | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    assignee = normalize_str(assignee_value) or owner
    assignee_user_soeid = normalize_str(assignee_user_soeid_value) or None
    if assignee_user_soeid is None:
        if owner_user_soeid and assignee == owner:
            assignee_user_soeid = owner_user_soeid
        elif current_soeid and assignee in {display_name, current_soeid}:
            assignee_user_soeid = current_soeid
    return assignee, assignee_user_soeid


def ensure_project_exists(session: Session, project_id: str, space_ctx: SpaceContext) -> None:
    exists = (
        session.query(Project)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .first()
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def get_solution_or_404(session: Session, solution_id: str, space_ctx: SpaceContext) -> Solution:
    solution = (
        solution_query(session, space_ctx)
        .filter(Solution.solution_id == solution_id)
        .first()
    )
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
    return solution


def enabled_phase_ids(session: Session, solution_id: str) -> set[str]:
    rows = (
        session.query(SolutionPhase.phase_id)
        .filter(SolutionPhase.solution_id == solution_id)
        .filter(SolutionPhase.is_enabled)
        .all()
    )
    return {r[0] for r in rows}


def last_enabled_phase_id(session: Session, solution_id: str) -> Optional[str]:
    sort_key = func.coalesce(SolutionPhase.sequence_override, Phase.sequence)
    row = (
        session.query(SolutionPhase.phase_id)
        .join(Phase, Phase.phase_id == SolutionPhase.phase_id)
        .filter(SolutionPhase.solution_id == solution_id)
        .filter(SolutionPhase.is_enabled)
        .order_by(sort_key.desc(), Phase.sequence.desc(), SolutionPhase.solution_phase_id.desc())
        .first()
    )
    return row[0] if row else None


def validate_current_phase(session: Session, solution_id: str, current_phase: Optional[str]) -> None:
    if not current_phase:
        return
    phase_exists = session.query(Phase).filter(Phase.phase_id == current_phase).first()
    if not phase_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"current_phase '{current_phase}' does not exist",
        )
    enabled = enabled_phase_ids(session, solution_id)
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No phases enabled for this solution; current_phase must be null",
        )
    if current_phase not in enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="current_phase must be one of the enabled phases for this solution",
        )


def apply_solution_completion_state(
    session: Session,
    solution: Solution,
    *,
    next_status,
    now: datetime,
) -> None:
    raw_status = next_status.value if hasattr(next_status, "value") else str(next_status)
    if raw_status == "complete":
        solution.completed_at = solution.completed_at or now
        if not solution.current_phase:
            solution.current_phase = last_enabled_phase_id(session, solution.solution_id)
        return
    solution.completed_at = None


def run_enable_all_phases(session: Session, solution_id: str) -> None:
    enable_all_phases(session, solution_id)


def is_done_status(status_value: TaskStatus | str | None) -> bool:
    if status_value is None:
        return False
    if status_value in DONE_STATUSES:
        return True
    raw = status_value.value if hasattr(status_value, "value") else str(status_value)
    return raw in {TaskStatus.complete.value, TaskStatus.abandoned.value}


def task_actionability(task: Task) -> dict:
    today = datetime.now(timezone.utc).date()
    is_done = is_done_status(task.status)
    due_date = task.due_date
    updated_date = task.updated_at.date() if task.updated_at else today

    is_overdue = bool(due_date and due_date < today and not is_done)
    is_due_soon = bool(
        due_date and not is_done and 0 <= (due_date - today).days <= DUE_SOON_DAYS
    )
    is_stale = bool(not is_done and (today - updated_date).days > STALE_DAYS)

    urgency_score = 0.0
    if not is_done:
        priority = max(1, min(5, int(task.priority or 3)))
        priority_score = (6 - priority) * 15

        due_score = 0
        if due_date:
            days_to_due = (due_date - today).days
            if days_to_due < 0:
                due_score = 45
            elif days_to_due <= DUE_SOON_DAYS:
                due_score = max(8, (DUE_SOON_DAYS - days_to_due + 1) * 2)

        blocked_score = 18 if task.blocked else 0
        stale_score = 10 if is_stale else 0
        urgency_score = float(min(100, priority_score + due_score + blocked_score + stale_score))

    return {
        "is_overdue": is_overdue,
        "is_due_soon": is_due_soon,
        "is_stale": is_stale,
        "urgency_score": round(urgency_score, 2),
    }


def task_payload(
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
    payload.update(task_actionability(task))
    return payload


def apply_task_completion_state(
    task: Task,
    *,
    next_status: TaskStatus,
    now: datetime,
) -> None:
    if next_status == TaskStatus.complete:
        task.completed_at = task.completed_at or now
        return
    task.completed_at = None


def resolve_task_assignee(
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


def publish_task_mutation(space_id: str) -> None:
    publish_space_mutation(
        space_id,
        ["tasks"],
        broadcast_channel="tasks",
    )


def publish_task_import(
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
    publish_task_mutation(space_id)


def task_solution_query(session: Session, space_ctx: SpaceContext):
    return solution_query(session, space_ctx)


def task_project_query(session: Session, space_ctx: SpaceContext):
    return project_query(session, space_ctx)


def task_query(session: Session, space_ctx: SpaceContext):
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


def solution_repo_map(session: Session, space_ctx: SpaceContext, solution_ids: list[str]) -> dict[str, Optional[str]]:
    valid_ids = [solution_id for solution_id in solution_ids if solution_id]
    if not valid_ids:
        return {}
    rows = (
        solution_query(session, space_ctx)
        .filter(Solution.solution_id.in_(valid_ids))
        .all()
    )
    return {row.solution_id: row.github_repo_url for row in rows}


def ensure_solution(session: Session, solution_id: str, space_ctx: SpaceContext) -> Solution:
    solution = (
        solution_query(session, space_ctx)
        .filter(Solution.solution_id == solution_id)
        .first()
    )
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
    return solution


def get_task(session: Session, task_id: str, space_ctx: SpaceContext) -> Task:
    task = (
        task_query(session, space_ctx)
        .filter(Task.task_id == task_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task
