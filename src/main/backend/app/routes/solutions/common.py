from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models import Phase, Project, Solution, SolutionPhase
from ...schemas import SolutionRead
from ...services.github_repo_urls import normalize_github_repo_url
from ...services.spaces import SpaceContext
from ...utils import enable_all_phases, normalize_str, read_text_value
from ...utils.enums import RagStatus, SolutionStatus
from .._mutations import publish_space_mutation

_SOLUTIONS_LIST_TTL_SECONDS = 20
_SOLUTIONS_DETAIL_TTL_SECONDS = 30
_WORK_ALLOCATION_PROJECT_NAME_PREFIX = "Work Allocation Board ["


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _solution_payload(solution: Solution) -> dict:
    return SolutionRead.model_validate(solution).model_dump(mode="json")


def _publish_solution_mutation(
    space_id: str,
    *,
    invalidate_subcomponents: bool = False,
) -> None:
    cache_keys = ["solutions"]
    if invalidate_subcomponents:
        cache_keys.append("subcomponents")
    publish_space_mutation(
        space_id,
        cache_keys,
        broadcast_channel="solutions",
    )
    if invalidate_subcomponents:
        publish_space_mutation(
            space_id,
            ["subcomponents"],
            broadcast_channel="subcomponents",
        )


def _publish_solution_deletion(space_id: str) -> None:
    _publish_solution_mutation(
        space_id,
        invalidate_subcomponents=True,
    )


def _publish_solution_import(
    space_id: str,
    *,
    projects_created: int,
    invalidate_subcomponents: bool = False,
) -> None:
    if projects_created > 0:
        publish_space_mutation(
            space_id,
            ["projects"],
            broadcast_channel="projects",
        )
    _publish_solution_mutation(
        space_id,
        invalidate_subcomponents=invalidate_subcomponents,
    )


def _parse_rag_status(raw: Optional[str]) -> Optional[RagStatus]:
    value = normalize_str(raw).lower()
    if not value:
        return None
    for candidate in RagStatus:
        if candidate.value == value:
            return candidate
    raise ValueError(f"invalid rag_status '{raw}', expected one of: red, amber, green")


def _ensure_project_exists(session: Session, project_id: str, space_ctx: SpaceContext) -> None:
    exists = (
        session.query(Project)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .first()
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


def _solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _work_allocation_project_id_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project.project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.project_name.like(f"{_WORK_ALLOCATION_PROJECT_NAME_PREFIX}%"))
    )


def _exclude_work_allocation_board_solutions(query, session: Session, space_ctx: SpaceContext):
    return query.filter(~Solution.project_id.in_(_work_allocation_project_id_query(session, space_ctx)))


def _get_solution_or_404(session: Session, solution_id: str, space_ctx: SpaceContext) -> Solution:
    solution = (
        _solution_query(session, space_ctx)
        .filter(Solution.solution_id == solution_id)
        .first()
    )
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
    return solution


def _enabled_phase_ids(session: Session, solution_id: str) -> set[str]:
    rows = (
        session.query(SolutionPhase.phase_id)
        .filter(SolutionPhase.solution_id == solution_id)
        .filter(SolutionPhase.is_enabled == True)
        .all()
    )
    return {r[0] for r in rows}


def _last_enabled_phase_id(session: Session, solution_id: str) -> Optional[str]:
    sort_key = func.coalesce(SolutionPhase.sequence_override, Phase.sequence)
    row = (
        session.query(SolutionPhase.phase_id)
        .join(Phase, Phase.phase_id == SolutionPhase.phase_id)
        .filter(SolutionPhase.solution_id == solution_id)
        .filter(SolutionPhase.is_enabled == True)
        .order_by(sort_key.desc(), Phase.sequence.desc(), SolutionPhase.solution_phase_id.desc())
        .first()
    )
    return row[0] if row else None


def _validate_current_phase(session: Session, solution_id: str, current_phase: Optional[str]) -> None:
    if not current_phase:
        return
    phase_exists = session.query(Phase).filter(Phase.phase_id == current_phase).first()
    if not phase_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"current_phase '{current_phase}' does not exist",
        )
    enabled = _enabled_phase_ids(session, solution_id)
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


def _apply_solution_completion_state(
    session: Session,
    solution: Solution,
    *,
    next_status: SolutionStatus,
    now: datetime,
) -> None:
    if next_status == SolutionStatus.complete:
        solution.completed_at = solution.completed_at or now
        if not solution.current_phase:
            solution.current_phase = _last_enabled_phase_id(session, solution.solution_id)
        return
    solution.completed_at = None


def _run_enable_all_phases(session: Session, solution_id: str) -> None:
    from . import enable_all_phases as enable_all_phases_hook

    enable_all_phases_hook(session, solution_id)


__all__ = [
    "_SOLUTIONS_DETAIL_TTL_SECONDS",
    "_SOLUTIONS_LIST_TTL_SECONDS",
    "_apply_solution_completion_state",
    "_ensure_project_exists",
    "_exclude_work_allocation_board_solutions",
    "_get_solution_or_404",
    "_parse_rag_status",
    "_publish_solution_deletion",
    "_publish_solution_import",
    "_publish_solution_mutation",
    "_role_scope",
    "_run_enable_all_phases",
    "_solution_payload",
    "_solution_query",
    "_validate_current_phase",
    "enable_all_phases",
    "normalize_github_repo_url",
    "read_text_value",
]
