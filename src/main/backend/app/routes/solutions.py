import csv
from datetime import date, datetime, timezone
from io import StringIO
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..utils.enums import (
    ConfidenceLevel,
    ProjectStatus,
    RagStatus,
    SolutionStatus,
)
from ..models import Phase, Project, Solution, SolutionPhase, User
from ..schemas import SolutionCreate, SolutionRead, SolutionUpdate
from ..utils import (
    enable_all_phases,
    normalize_status,
    normalize_str,
    parse_date,
    parse_priority,
    read_csv,
)
from ..services.realtime import schedule_broadcast
from ..services.audit_log import log_changes
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token

router = APIRouter()
_SOLUTIONS_LIST_TTL_SECONDS = 20
_SOLUTIONS_DETAIL_TTL_SECONDS = 30


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _solution_payload(solution: Solution) -> dict:
    return SolutionRead.model_validate(solution).model_dump(mode="json")


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
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
    )


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
        .filter(SolutionPhase.is_enabled.is_(True))
        .all()
    )
    return {r[0] for r in rows}


def _last_enabled_phase_id(session: Session, solution_id: str) -> Optional[str]:
    sort_key = func.coalesce(SolutionPhase.sequence_override, Phase.sequence)
    row = (
        session.query(SolutionPhase.phase_id)
        .join(Phase, Phase.phase_id == SolutionPhase.phase_id)
        .filter(SolutionPhase.solution_id == solution_id)
        .filter(SolutionPhase.is_enabled.is_(True))
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


@router.get(
    "/solutions",
    response_model=List[SolutionRead],
)
def list_all_solutions(
    project_id: Optional[str] = None,
    status_filter: Optional[SolutionStatus] = Query(None, alias="status"),
    owner: Optional[str] = None,
    assignee: Optional[str] = None,
    owner_user_soeid: Optional[str] = None,
    assignee_user_soeid: Optional[str] = None,
    phase: Optional[str] = None,
    priority: Optional[int] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    status_val = status_filter.value if hasattr(status_filter, "value") else status_filter
    owner_norm = owner.strip().lower() if owner else None
    assignee_norm = assignee.strip().lower() if assignee else None
    params = {
        "project_id": project_id,
        "status": status_val,
        "owner": owner_norm,
        "assignee": assignee_norm,
        "owner_user_soeid": owner_user_soeid,
        "assignee_user_soeid": assignee_user_soeid,
        "phase": phase,
        "priority": priority,
        "due_before": due_before.isoformat() if due_before else None,
        "due_after": due_after.isoformat() if due_after else None,
    }
    scope_token = make_scope_token("solutions", space_ctx.space_id)

    def _load():
        query = _solution_query(session, space_ctx)
        if project_id:
            query = query.filter(Solution.project_id == project_id)
        if status_filter:
            query = query.filter(Solution.status == status_filter)
        if owner_norm:
            query = query.filter(func.lower(Solution.owner) == owner_norm)
        if assignee_norm:
            query = query.filter(func.lower(Solution.assignee) == assignee_norm)
        if owner_user_soeid:
            query = query.filter(Solution.owner_user_soeid == owner_user_soeid)
        if assignee_user_soeid:
            query = query.filter(Solution.assignee_user_soeid == assignee_user_soeid)
        if phase:
            query = query.filter(Solution.current_phase == phase)
        if priority is not None:
            query = query.filter(Solution.priority == priority)
        if due_before:
            query = query.filter(Solution.due_date <= due_before)
        if due_after:
            query = query.filter(Solution.due_date >= due_after)
        rows = query.order_by(Solution.priority.asc(), Solution.created_at.asc()).all()
        return [_solution_payload(row) for row in rows]

    return cached_call(
        endpoint="solutions:list_all",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_SOLUTIONS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get(
    "/projects/{project_id}/solutions",
    response_model=List[SolutionRead],
)
def list_solutions(
    project_id: str,
    status_filter: Optional[SolutionStatus] = Query(None, alias="status"),
    owner: Optional[str] = None,
    assignee: Optional[str] = None,
    owner_user_soeid: Optional[str] = None,
    assignee_user_soeid: Optional[str] = None,
    phase: Optional[str] = None,
    priority: Optional[int] = None,
    due_before: Optional[date] = None,
    due_after: Optional[date] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    _ensure_project_exists(session, project_id, space_ctx)
    status_val = status_filter.value if hasattr(status_filter, "value") else status_filter
    owner_norm = owner.strip().lower() if owner else None
    assignee_norm = assignee.strip().lower() if assignee else None
    params = {
        "project_id": project_id,
        "status": status_val,
        "owner": owner_norm,
        "assignee": assignee_norm,
        "owner_user_soeid": owner_user_soeid,
        "assignee_user_soeid": assignee_user_soeid,
        "phase": phase,
        "priority": priority,
        "due_before": due_before.isoformat() if due_before else None,
        "due_after": due_after.isoformat() if due_after else None,
    }
    scope_token = make_scope_token("solutions", space_ctx.space_id)

    def _load():
        query = _solution_query(session, space_ctx).filter(Solution.project_id == project_id)
        if status_filter:
            query = query.filter(Solution.status == status_filter)
        if owner_norm:
            query = query.filter(func.lower(Solution.owner) == owner_norm)
        if assignee_norm:
            query = query.filter(func.lower(Solution.assignee) == assignee_norm)
        if owner_user_soeid:
            query = query.filter(Solution.owner_user_soeid == owner_user_soeid)
        if assignee_user_soeid:
            query = query.filter(Solution.assignee_user_soeid == assignee_user_soeid)
        if phase:
            query = query.filter(Solution.current_phase == phase)
        if priority is not None:
            query = query.filter(Solution.priority == priority)
        if due_before:
            query = query.filter(Solution.due_date <= due_before)
        if due_after:
            query = query.filter(Solution.due_date >= due_after)
        return [_solution_payload(row) for row in query.all()]

    return cached_call(
        endpoint="solutions:list_by_project",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_SOLUTIONS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


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
):
    _ensure_project_exists(session, project_id, space_ctx)

    current_phase = normalize_str(payload.current_phase) or None
    if current_phase:
        phase_exists = session.query(Phase).filter(Phase.phase_id == current_phase).first()
        if not phase_exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"current_phase '{current_phase}' does not exist",
            )

    version = normalize_str(payload.version) or "0.1.0"
    owner = normalize_str(payload.owner) or current_user.display_name or current_user.soeid or ""
    owner_user_soeid = normalize_str(payload.owner_user_soeid) or None
    if owner_user_soeid is None and current_user.soeid:
        if owner == current_user.display_name or owner == current_user.soeid:
            owner_user_soeid = current_user.soeid

    assignee = normalize_str(payload.assignee) or owner
    assignee_user_soeid = normalize_str(payload.assignee_user_soeid) or None
    if assignee_user_soeid is None and current_user.soeid:
        if assignee == current_user.display_name or assignee == current_user.soeid:
            assignee_user_soeid = current_user.soeid

    conflict = (
        _solution_query(session, space_ctx)
        .filter(Solution.project_id == project_id)
        .filter(Solution.solution_name == payload.solution_name)
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
        solution_name=payload.solution_name,
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
    log_changes(
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
    session.commit()
    session.refresh(solution)
    enable_all_phases(session, solution.solution_id)
    session.refresh(solution)
    invalidate_space(space_ctx.space_id, ["solutions"])
    schedule_broadcast("solutions")
    return solution


@router.post("/solutions/import")
def import_solutions(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"created": 0, "updated": 0, "projects_created": 0, "errors": errors, "total_rows": 0}
    created = updated = projects_created = 0
    seen = set()
    request_id = str(uuid4())

    projects_by_name = {
        p.project_name.lower(): p
        for p in (
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.space_id == space_ctx.space_id)
            .all()
        )
    }

    for idx, row in enumerate(rows, start=2):
        project_name = normalize_str(row.get("project_name"))
        solution_name = normalize_str(row.get("solution_name"))
        version_raw = normalize_str(row.get("version")) or "0.1.0"
        owner = normalize_str(row.get("owner"))
        assignee = normalize_str(row.get("assignee"))
        owner_user_soeid = normalize_str(row.get("owner_user_soeid")) or None
        assignee_user_soeid = normalize_str(row.get("assignee_user_soeid")) or None
        approver = normalize_str(row.get("approver")) or None
        approver_user_soeid = normalize_str(row.get("approver_user_soeid")) or None
        key_stakeholder = normalize_str(row.get("key_stakeholder"))
        if not project_name or not solution_name or not owner:
            errors.append(f"Row {idx}: project_name, solution_name, and owner are required")
            continue
        key = (project_name.lower(), solution_name.lower(), version_raw.lower())
        if key in seen:
            errors.append(
                f"Row {idx}: duplicate solution '{solution_name}' version '{version_raw}' for project '{project_name}' in CSV (strict-first policy)"
            )
            continue
        seen.add(key)
        try:
            status_enum = normalize_status(
                row.get("status") or SolutionStatus.not_started.value, SolutionStatus
            )
            priority_val = parse_priority(row.get("priority"), default=3)
            due_date_val = parse_date(row.get("due_date"))
            planned_start_date = parse_date(row.get("planned_start_date"))
            rag_status_raw = _parse_rag_status(row.get("rag_status"))
            rag_confidence = (
                float(row.get("rag_confidence")) if normalize_str(row.get("rag_confidence")) else None
            )
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue

        description = normalize_str(row.get("description")) or None
        success_criteria = normalize_str(row.get("success_criteria")) or None
        problem_statement = normalize_str(row.get("problem_statement")) or None
        rag_reason_val = normalize_str(row.get("rag_reason")) or None
        current_phase = normalize_str(row.get("current_phase")) or None
        if current_phase:
            phase_exists = session.query(Phase).filter(Phase.phase_id == current_phase).first()
            if not phase_exists:
                errors.append(f"Row {idx}: current_phase '{current_phase}' does not exist")
                continue
        blockers = normalize_str(row.get("blockers")) or None
        risks = normalize_str(row.get("risks")) or None

        rag_status_val = rag_status_raw or RagStatus.green
        impact_confidence = None
        impact_conf_raw = normalize_str(row.get("impact_confidence"))
        if impact_conf_raw:
            for candidate in ConfidenceLevel:
                if candidate.value.lower() == impact_conf_raw.lower():
                    impact_confidence = candidate
                    break
            if impact_confidence is None:
                errors.append(f"Row {idx}: invalid impact_confidence '{impact_conf_raw}'")
                continue

        project = projects_by_name.get(project_name.lower())
        if not project:
            project = Project(
                space_id=space_ctx.space_id,
                project_name=project_name,
                status=ProjectStatus.not_started,
                description=None,
            )
            session.add(project)
            session.flush()  # ensure project_id is available
            projects_by_name[project_name.lower()] = project
            projects_created += 1
            log_changes(
                session,
                entity_type="project",
                entity_id=project.project_id,
                user_id=current_user.user_id,
                action="create",
                space_id=space_ctx.space_id,
                changes={
                    "project_name": (None, project.project_name),
                    "status": (None, project.status),
                    "description": (None, project.description),
                    "success_criteria": (None, project.success_criteria),
                },
                request_id=request_id,
            )

        existing = (
            _solution_query(session, space_ctx)
            .filter(Solution.project_id == project.project_id)
            .filter(Solution.solution_name == solution_name)
            .filter(Solution.version == version_raw)
            .first()
        )
        try:
            if existing:
                if current_phase:
                    _validate_current_phase(session, existing.solution_id, current_phase)

                before = {
                    "status": existing.status,
                    "rag_status": existing.rag_status,
                    "rag_reason": existing.rag_reason,
                    "priority": existing.priority,
                    "due_date": existing.due_date,
                    "planned_start_date": existing.planned_start_date,
                    "current_phase": existing.current_phase,
                    "description": existing.description,
                    "success_criteria": existing.success_criteria,
                    "problem_statement": existing.problem_statement,
                    "impact_confidence": existing.impact_confidence,
                    "owner": existing.owner,
                    "owner_user_soeid": existing.owner_user_soeid,
                    "assignee": existing.assignee,
                    "assignee_user_soeid": existing.assignee_user_soeid,
                    "approver": existing.approver,
                    "approver_user_soeid": existing.approver_user_soeid,
                    "key_stakeholder": existing.key_stakeholder,
                    "blockers": existing.blockers,
                    "risks": existing.risks,
                    "rag_confidence": existing.rag_confidence,
                    "completed_at": existing.completed_at,
                }
                now = datetime.now(timezone.utc)
                existing.status = status_enum
                existing.rag_status = rag_status_val
                existing.rag_reason = rag_reason_val
                existing.priority = priority_val
                existing.due_date = due_date_val
                existing.planned_start_date = planned_start_date
                existing.current_phase = current_phase
                existing.description = description
                existing.success_criteria = success_criteria
                existing.problem_statement = problem_statement
                existing.impact_confidence = impact_confidence
                existing.owner = owner
                existing.owner_user_soeid = owner_user_soeid
                existing.assignee = assignee or ""
                existing.assignee_user_soeid = assignee_user_soeid
                existing.approver = approver
                existing.approver_user_soeid = approver_user_soeid
                existing.key_stakeholder = key_stakeholder or None
                existing.blockers = blockers
                existing.risks = risks
                existing.rag_confidence = rag_confidence
                if not existing.space_id:
                    existing.space_id = space_ctx.space_id
                if status_enum == SolutionStatus.complete and not existing.completed_at:
                    existing.completed_at = now
                    if not existing.current_phase:
                        existing.current_phase = _last_enabled_phase_id(session, existing.solution_id)
                existing.updated_at = now
                session.add(existing)
                log_changes(
                    session,
                    entity_type="solution",
                    entity_id=existing.solution_id,
                    user_id=current_user.user_id,
                    action="update",
                    space_id=space_ctx.space_id,
                    changes={
                        "status": (before["status"], existing.status),
                        "rag_status": (before["rag_status"], existing.rag_status),
                        "rag_reason": (before["rag_reason"], existing.rag_reason),
                        "priority": (before["priority"], existing.priority),
                        "due_date": (before["due_date"], existing.due_date),
                        "planned_start_date": (before["planned_start_date"], existing.planned_start_date),
                        "current_phase": (before["current_phase"], existing.current_phase),
                        "description": (before["description"], existing.description),
                        "success_criteria": (before["success_criteria"], existing.success_criteria),
                        "problem_statement": (before["problem_statement"], existing.problem_statement),
                        "impact_confidence": (before["impact_confidence"], existing.impact_confidence),
                        "owner": (before["owner"], existing.owner),
                        "owner_user_soeid": (before["owner_user_soeid"], existing.owner_user_soeid),
                        "assignee": (before["assignee"], existing.assignee),
                        "assignee_user_soeid": (before["assignee_user_soeid"], existing.assignee_user_soeid),
                        "approver": (before["approver"], existing.approver),
                        "approver_user_soeid": (before["approver_user_soeid"], existing.approver_user_soeid),
                        "key_stakeholder": (before["key_stakeholder"], existing.key_stakeholder),
                        "blockers": (before["blockers"], existing.blockers),
                        "risks": (before["risks"], existing.risks),
                        "rag_confidence": (before["rag_confidence"], existing.rag_confidence),
                        "completed_at": (before["completed_at"], existing.completed_at),
                    },
                    request_id=request_id,
                )
                updated += 1
                session.commit()
            else:
                now = datetime.now(timezone.utc)
                completed_at = now if status_enum == SolutionStatus.complete else None
                solution = Solution(
                    space_id=space_ctx.space_id,
                    project_id=project.project_id,
                    solution_name=solution_name,
                    version=version_raw,
                    status=status_enum,
                    rag_status=rag_status_val,
                    rag_reason=rag_reason_val,
                    rag_confidence=rag_confidence,
                    priority=priority_val,
                    due_date=due_date_val,
                    planned_start_date=planned_start_date,
                    current_phase=current_phase,
                    description=description,
                    success_criteria=success_criteria,
                    problem_statement=problem_statement,
                    impact_confidence=impact_confidence,
                    owner=owner,
                    owner_user_soeid=owner_user_soeid,
                    assignee=assignee or "",
                    assignee_user_soeid=assignee_user_soeid,
                    approver=approver,
                    approver_user_soeid=approver_user_soeid,
                    key_stakeholder=key_stakeholder or None,
                    blockers=blockers,
                    risks=risks,
                    completed_at=completed_at,
                )
                session.add(solution)
                session.flush()
                log_changes(
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
                        "rag_confidence": (None, solution.rag_confidence),
                        "priority": (None, solution.priority),
                        "due_date": (None, solution.due_date),
                        "planned_start_date": (None, solution.planned_start_date),
                        "current_phase": (None, solution.current_phase),
                        "description": (None, solution.description),
                        "success_criteria": (None, solution.success_criteria),
                        "problem_statement": (None, solution.problem_statement),
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
                        "completed_at": (None, solution.completed_at),
                    },
                    request_id=request_id,
                )
                session.commit()
                enable_all_phases(session, solution.solution_id)
                created += 1
        except Exception as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")
    invalidate_space(space_ctx.space_id, ["solutions"])
    schedule_broadcast("solutions")
    return {
        "created": created,
        "updated": updated,
        "projects_created": projects_created,
        "errors": errors,
        "total_rows": len(rows),
    }


@router.get("/solutions/export")
def export_solutions(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    solutions = _solution_query(session, space_ctx).all()
    project_map = {
        p.project_id: p.project_name
        for p in (
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.space_id == space_ctx.space_id)
        )
    }
    buffer = StringIO()
    fieldnames = [
        "project_name",
        "solution_name",
        "version",
        "status",
        "rag_status",
        "rag_reason",
        "rag_confidence",
        "priority",
        "due_date",
        "planned_start_date",
        "current_phase",
        "description",
        "problem_statement",
        "success_criteria",
        "impact_confidence",
        "owner",
        "owner_user_soeid",
        "assignee",
        "assignee_user_soeid",
        "approver",
        "approver_user_soeid",
        "key_stakeholder",
        "blockers",
        "risks",
        "completed_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for s in solutions:
        writer.writerow(
            {
                "project_name": project_map.get(s.project_id, ""),
                "solution_name": s.solution_name,
                "version": s.version,
                "status": s.status.value if hasattr(s.status, "value") else s.status,
                "rag_status": s.rag_status.value if hasattr(s.rag_status, "value") else s.rag_status,
                "rag_reason": s.rag_reason or "",
                "rag_confidence": s.rag_confidence if s.rag_confidence is not None else "",
                "priority": s.priority,
                "due_date": s.due_date.isoformat() if s.due_date else "",
                "planned_start_date": s.planned_start_date.isoformat() if s.planned_start_date else "",
                "current_phase": s.current_phase or "",
                "description": s.description or "",
                "problem_statement": s.problem_statement or "",
                "success_criteria": s.success_criteria or "",
                "impact_confidence": s.impact_confidence.value if hasattr(s.impact_confidence, "value") else (s.impact_confidence or ""),
                "owner": s.owner or "",
                "owner_user_soeid": s.owner_user_soeid or "",
                "assignee": s.assignee or "",
                "assignee_user_soeid": s.assignee_user_soeid or "",
                "approver": s.approver or "",
                "approver_user_soeid": s.approver_user_soeid or "",
                "key_stakeholder": s.key_stakeholder or "",
                "blockers": s.blockers or "",
                "risks": s.risks or "",
                "completed_at": s.completed_at.isoformat() if s.completed_at else "",
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename=\"solutions.csv\"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)


@router.get("/solutions/{solution_id}", response_model=SolutionRead)
def get_solution(
    solution_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    scope_token = make_scope_token("solutions", space_ctx.space_id)

    def _load():
        return _solution_payload(_get_solution_or_404(session, solution_id, space_ctx))

    return cached_call(
        endpoint="solutions:detail",
        params={"solution_id": solution_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_SOLUTIONS_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.patch("/solutions/{solution_id}", response_model=SolutionRead)
def update_solution(
    solution_id: str,
    payload: SolutionUpdate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    solution = _get_solution_or_404(session, solution_id, space_ctx)

    update_data = payload.model_dump(exclude_unset=True)
    rag_updates = {k: update_data.pop(k) for k in list(update_data.keys()) if k in {"rag_status", "rag_reason"}}
    if "priority" in update_data:
        update_data["priority"] = parse_priority(update_data["priority"], default=3)
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "current_phase" in update_data:
        update_data["current_phase"] = normalize_str(update_data["current_phase"]) or None
        if update_data["current_phase"]:
            _validate_current_phase(session, solution.solution_id, update_data["current_phase"])

    fields_to_compare = set(update_data.keys()) | {"rag_status", "rag_reason"}
    before = {field: getattr(solution, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(solution, field, value)
    solution.updated_at = datetime.now(timezone.utc)

    if "status" in update_data and update_data["status"] == SolutionStatus.complete:
        solution.completed_at = solution.completed_at or datetime.now(timezone.utc)
        if not solution.current_phase:
            solution.current_phase = _last_enabled_phase_id(session, solution.solution_id)
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
        log_changes(
            session,
            entity_type="solution",
            entity_id=solution.solution_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes=changes,
        )
    session.commit()
    session.refresh(solution)
    invalidate_space(space_ctx.space_id, ["solutions"])
    schedule_broadcast("solutions")
    return solution


@router.delete("/solutions/{solution_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_solution(
    solution_id: str,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    solution = _get_solution_or_404(session, solution_id, space_ctx)
    now = datetime.now(timezone.utc)
    solution.deleted_at = now
    solution.updated_at = now
    session.add(solution)
    log_changes(
        session,
        entity_type="solution",
        entity_id=solution.solution_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    session.commit()
    invalidate_space(space_ctx.space_id, ["solutions"])
    schedule_broadcast("solutions")
    return None
