from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_db, current_user as current_user_dep, current_space as current_space_dep, require_space_role
from ..models import Phase, Project, Solution, SolutionPhase, User
from ..schemas import PhaseRead, SolutionPhaseInput, SolutionPhaseRead
from ..services.audit_log import log_changes
from ..services.spaces import SpaceContext
from ._mutations import publish_space_mutation

router = APIRouter()


def _active_solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


@router.get("/phases", response_model=List[PhaseRead])
def list_phases(session: Session = Depends(get_db)):
    phases = session.query(Phase).order_by(Phase.sequence.asc()).all()
    return phases


@router.post(
    "/solutions/{solution_id}/phases",
    response_model=List[SolutionPhaseRead],
)
def set_solution_phases(
    solution_id: str,
    payload: dict,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    """
    Upsert enabled phases for a solution. Payload shape:
    { "phases": [{ "phase_id": "...", "is_enabled": true/false, "sequence_override": 2 }]}
    """
    _ensure_solution_exists(session, solution_id, space_ctx)
    phases_data = payload.get("phases", [])
    if not isinstance(phases_data, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="phases must be a list"
        )

    now = datetime.now(timezone.utc)
    updated_items: list[SolutionPhase] = []

    for item in phases_data:
        data = SolutionPhaseInput.model_validate(item)

        phase_exists = session.query(Phase).filter(Phase.phase_id == data.phase_id).first()
        if not phase_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Phase {data.phase_id} does not exist",
            )

        sp = (
            session.query(SolutionPhase)
            .filter(SolutionPhase.solution_id == solution_id)
            .filter(SolutionPhase.phase_id == data.phase_id)
            .first()
        )
        action = "update" if sp else "create"
        before_enabled = sp.is_enabled if sp else None
        before_seq = sp.sequence_override if sp else None
        if sp:
            sp.is_enabled = data.is_enabled
            sp.sequence_override = data.sequence_override
            sp.updated_at = now
        else:
            sp = SolutionPhase(
                solution_id=solution_id,
                phase_id=data.phase_id,
                is_enabled=data.is_enabled,
                sequence_override=data.sequence_override,
                created_at=now,
                updated_at=now,
            )
            session.add(sp)
            session.flush()
        log_changes(
            session,
            entity_type="solution_phase",
            entity_id=sp.solution_phase_id,
            user_id=current_user.user_id,
            action=action,
            space_id=space_ctx.space_id,
            changes={
                "is_enabled": (before_enabled, sp.is_enabled),
                "sequence_override": (before_seq, sp.sequence_override),
            },
        )
        updated_items.append(sp)

    # If the solution's current_phase is now disabled, clear it to avoid invalid states.
    session.flush()
    solution = _active_solution_query(session, space_ctx).filter(Solution.solution_id == solution_id).first()
    if solution and solution.current_phase:
        enabled_ids = {
            row[0]
            for row in session.query(SolutionPhase.phase_id)
            .filter(SolutionPhase.solution_id == solution_id)
            .filter(SolutionPhase.is_enabled == True)
            .all()
        }
        if solution.current_phase not in enabled_ids:
            before_phase = solution.current_phase
            solution.current_phase = None
            solution.updated_at = now
            session.add(solution)
            log_changes(
                session,
                entity_type="solution",
                entity_id=solution.solution_id,
                user_id=current_user.user_id,
                action="update",
                space_id=space_ctx.space_id,
                changes={"current_phase": (before_phase, solution.current_phase)},
            )
    session.commit()
    publish_space_mutation(
        space_ctx.space_id,
        ["solutions"],
        broadcast_channel="solutions",
    )
    return _ordered_solution_phases(session, solution_id, space_ctx)


@router.get(
    "/solutions/{solution_id}/phases",
    response_model=List[SolutionPhaseRead],
)
def list_solution_phases(
    solution_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    _ensure_solution_exists(session, solution_id, space_ctx)
    return _ordered_solution_phases(session, solution_id, space_ctx)


def _ensure_solution_exists(session: Session, solution_id: str, space_ctx: SpaceContext) -> None:
    exists = _active_solution_query(session, space_ctx).filter(Solution.solution_id == solution_id).first()
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")


def _ordered_solution_phases(session: Session, solution_id: str, space_ctx: SpaceContext) -> list[SolutionPhase]:
    sort_key = func.coalesce(SolutionPhase.sequence_override, Phase.sequence)
    items = (
        session.query(SolutionPhase)
        .join(Solution, Solution.solution_id == SolutionPhase.solution_id)
        .join(Project, Project.project_id == Solution.project_id)
        .join(Phase, Phase.phase_id == SolutionPhase.phase_id)
        .filter(SolutionPhase.solution_id == solution_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .order_by(sort_key.asc(), Phase.sequence.asc(), SolutionPhase.solution_phase_id.asc())
        .all()
    )
    return items
