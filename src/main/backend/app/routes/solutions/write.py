from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_space_role
from ...models import Phase, Solution, User
from ...schemas import SolutionCreate, SolutionRead, SolutionUpdate
from ...services.audit_log import safe_log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_str, parse_priority
from ...utils.enums import RagStatus, SolutionStatus
from .._mutations import commit_refresh_and_publish, commit_session
from .common import (
    _apply_solution_completion_state,
    _ensure_project_exists,
    _get_solution_or_404,
    _publish_solution_deletion,
    _publish_solution_mutation,
    _resolve_solution_assignee,
    _resolve_solution_owner,
    _run_enable_all_phases,
    _solution_payload,
    _solution_query,
    _validate_current_phase,
    normalize_github_repo_url,
)

router = APIRouter()


def _required_solution_name(value: object) -> str:
    solution_name = normalize_str(value)
    if not solution_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="solution_name is required",
        )
    return solution_name


def _required_solution_version(value: object) -> str:
    version = normalize_str(value)
    if not version:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="version is required",
        )
    return version


@router.post(
    "/projects/{project_id}/solutions",
    response_model=SolutionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_solution(
    project_id: str,
    payload: SolutionCreate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    _ensure_project_exists(session, project_id, space_ctx)
    solution_name = _required_solution_name(payload.solution_name)

    current_phase = normalize_str(payload.current_phase) or None
    if current_phase:
        phase_exists = session.query(Phase).filter(Phase.phase_id == current_phase).first()
        if not phase_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"current_phase '{current_phase}' does not exist",
            )

    version = normalize_str(payload.version) or "0.1.0"
    try:
        github_repo_url = normalize_github_repo_url(payload.github_repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    owner, owner_user_soeid = _resolve_solution_owner(
        payload.owner,
        payload.owner_user_soeid,
        current_user,
    )
    assignee, assignee_user_soeid = _resolve_solution_assignee(
        payload.assignee,
        payload.assignee_user_soeid,
        owner=owner,
        owner_user_soeid=owner_user_soeid,
        current_user=current_user,
    )

    conflict = (
        _solution_query(session, space_ctx)
        .filter(Solution.project_id == project_id)
        .filter(Solution.solution_name == solution_name)
        .filter(Solution.version == version)
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solution name and version already exist for this project",
        )

    now = datetime.now(timezone.utc)
    completed_at = now if payload.status == SolutionStatus.complete else None
    priority_val = parse_priority(payload.priority, default=3)

    rag_reason = normalize_str(payload.rag_reason) or None
    rag_status = payload.rag_status or RagStatus.green

    solution = Solution(
        space_id=space_ctx.space_id,
        project_id=project_id,
        solution_name=solution_name,
        version=version,
        status=payload.status,
        rag_status=rag_status,
        rag_reason=rag_reason,
        priority=priority_val,
        due_date=payload.due_date,
        planned_start_date=payload.planned_start_date,
        current_phase=current_phase,
        description=payload.description,
        success_criteria=payload.success_criteria,
        problem_statement=payload.problem_statement,
        github_repo_url=github_repo_url,
        impact_confidence=payload.impact_confidence,
        owner=owner,
        owner_user_soeid=owner_user_soeid,
        assignee=assignee or "",
        assignee_user_soeid=assignee_user_soeid,
        approver=payload.approver,
        approver_user_soeid=payload.approver_user_soeid,
        key_stakeholder=payload.key_stakeholder,
        blockers=payload.blockers,
        risks=payload.risks,
        rag_confidence=payload.rag_confidence,
        completed_at=completed_at,
        created_at=now,
        updated_at=now,
        capacity_hours=payload.capacity_hours or 0,
    )
    session.add(solution)
    session.flush()
    safe_log_changes(
        session,
        entity_type="solution",
        entity_id=solution.solution_id,
        user_id=current_user.user_id,
        action="create",
        space_id=space_ctx.space_id,
        changes={
            "solution_name": (None, solution.solution_name),
            "version": (None, solution.version),
            "status": (None, solution.status),
            "rag_status": (None, solution.rag_status),
            "rag_reason": (None, solution.rag_reason),
            "priority": (None, solution.priority),
            "due_date": (None, solution.due_date),
            "current_phase": (None, solution.current_phase),
            "description": (None, solution.description),
            "success_criteria": (None, solution.success_criteria),
            "problem_statement": (None, solution.problem_statement),
            "github_repo_url": (None, solution.github_repo_url),
            "impact_confidence": (None, solution.impact_confidence),
            "owner": (None, solution.owner),
            "owner_user_soeid": (None, solution.owner_user_soeid),
            "assignee": (None, solution.assignee),
            "assignee_user_soeid": (None, solution.assignee_user_soeid),
            "approver": (None, solution.approver),
            "approver_user_soeid": (None, solution.approver_user_soeid),
            "key_stakeholder": (None, solution.key_stakeholder),
            "blockers": (None, solution.blockers),
            "risks": (None, solution.risks),
            "rag_confidence": (None, solution.rag_confidence),
            "completed_at": (None, solution.completed_at),
        },
    )
    _run_enable_all_phases(session, solution.solution_id)
    commit_refresh_and_publish(
        session,
        solution,
        space_id=space_ctx.space_id,
        cache_keys=["solutions"],
        broadcast_channel="solutions",
    )
    return _solution_payload(solution)


@router.patch("/solutions/{solution_id}", response_model=SolutionRead)
def update_solution(
    solution_id: str,
    payload: SolutionUpdate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    solution = _get_solution_or_404(session, solution_id, space_ctx)

    update_data = payload.model_dump(exclude_unset=True)
    rag_updates = {k: update_data.pop(k) for k in list(update_data.keys()) if k in {"rag_status", "rag_reason"}}
    if "solution_name" in update_data:
        update_data["solution_name"] = _required_solution_name(update_data["solution_name"])
    if "version" in update_data:
        update_data["version"] = _required_solution_version(update_data["version"])
    if "priority" in update_data:
        update_data["priority"] = parse_priority(update_data["priority"], default=3)
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "github_repo_url" in update_data:
        try:
            update_data["github_repo_url"] = normalize_github_repo_url(update_data["github_repo_url"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    if "current_phase" in update_data:
        update_data["current_phase"] = normalize_str(update_data["current_phase"]) or None
        if update_data["current_phase"]:
            _validate_current_phase(session, solution.solution_id, update_data["current_phase"])

    fields_to_compare = set(update_data.keys()) | {"rag_status", "rag_reason"}
    if "status" in update_data:
        fields_to_compare.update({"completed_at", "current_phase"})
    before = {field: getattr(solution, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(solution, field, value)
    solution.updated_at = datetime.now(timezone.utc)

    if "status" in update_data:
        _apply_solution_completion_state(
            session,
            solution,
            next_status=update_data["status"],
            now=solution.updated_at,
        )
    if "rag_status" in rag_updates and rag_updates.get("rag_status") is not None:
        solution.rag_status = rag_updates["rag_status"]
    if "rag_reason" in rag_updates:
        solution.rag_reason = normalize_str(rag_updates["rag_reason"]) or None

    if any(k in update_data for k in ("solution_name", "version")):
        conflict = (
            _solution_query(session, space_ctx)
            .filter(Solution.project_id == solution.project_id)
            .filter(Solution.solution_name == solution.solution_name)
            .filter(Solution.version == solution.version)
            .filter(Solution.solution_id != solution.solution_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solution name and version already exist for this project",
            )

    session.add(solution)
    changes = {field: (before.get(field), getattr(solution, field)) for field in fields_to_compare}
    if changes:
        safe_log_changes(
            session,
            entity_type="solution",
            entity_id=solution.solution_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes=changes,
        )
    invalidate_subcomponents = (
        "github_repo_url" in update_data and before.get("github_repo_url") != solution.github_repo_url
    )
    commit_session(session)
    session.refresh(solution)
    _publish_solution_mutation(
        space_ctx.space_id,
        invalidate_subcomponents=invalidate_subcomponents,
    )
    return _solution_payload(solution)


@router.delete("/solutions/{solution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_solution(
    solution_id: str,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    solution = _get_solution_or_404(session, solution_id, space_ctx)
    now = datetime.now(timezone.utc)
    solution.deleted_at = now
    solution.updated_at = now
    session.add(solution)
    safe_log_changes(
        session,
        entity_type="solution",
        entity_id=solution.solution_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    commit_session(session)
    _publish_solution_deletion(space_ctx.space_id)
    return None
