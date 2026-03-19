import csv
from datetime import datetime, timezone, date, timedelta
from io import StringIO
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..utils.enums import ProjectStatus, SolutionStatus, SubcomponentStatus
from ..models import ChangeLog, Project, Solution, Subcomponent, User
from ..schemas import (
    ChangeLogRead,
    SubcomponentBatchUpdate,
    SubcomponentCreate,
    SubcomponentRead,
    SubcomponentUpdate,
)
from ..utils import (
    enable_all_phases,
    normalize_status,
    normalize_str,
    parse_date,
    parse_priority,
    read_csv,
)
from ..services.audit_log import log_changes
from ..services.github_repo_urls import normalize_github_repo_url, resolve_effective_github_repo_url
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, make_scope_token
from ._mutations import commit_refresh_and_publish, commit_session, publish_space_mutation

router = APIRouter()
_SUBCOMPONENTS_LIST_TTL_SECONDS = 20
_SUBCOMPONENTS_DETAIL_TTL_SECONDS = 30
_DUE_SOON_DAYS = 14
_STALE_DAYS = 7
_DONE_STATUSES = {SubcomponentStatus.complete, SubcomponentStatus.abandoned}


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _is_done_status(status_value: SubcomponentStatus | str | None) -> bool:
    if status_value is None:
        return False
    if status_value in _DONE_STATUSES:
        return True
    raw = status_value.value if hasattr(status_value, "value") else str(status_value)
    return raw in {SubcomponentStatus.complete.value, SubcomponentStatus.abandoned.value}


def _subcomponent_actionability(subcomponent: Subcomponent) -> dict:
    today = datetime.now(timezone.utc).date()
    is_done = _is_done_status(subcomponent.status)
    due_date = subcomponent.due_date
    updated_date = subcomponent.updated_at.date() if subcomponent.updated_at else today

    is_overdue = bool(due_date and due_date < today and not is_done)
    is_due_soon = bool(
        due_date and not is_done and 0 <= (due_date - today).days <= _DUE_SOON_DAYS
    )
    is_stale = bool(not is_done and (today - updated_date).days > _STALE_DAYS)

    urgency_score = 0.0
    if not is_done:
        priority = max(1, min(5, int(subcomponent.priority or 3)))
        priority_score = (6 - priority) * 15  # P1 is most urgent.

        due_score = 0
        if due_date:
            days_to_due = (due_date - today).days
            if days_to_due < 0:
                due_score = 45
            elif days_to_due <= _DUE_SOON_DAYS:
                due_score = max(8, (_DUE_SOON_DAYS - days_to_due + 1) * 2)

        blocked_score = 18 if subcomponent.blocked else 0
        stale_score = 10 if is_stale else 0
        urgency_score = float(min(100, priority_score + due_score + blocked_score + stale_score))

    return {
        "is_overdue": is_overdue,
        "is_due_soon": is_due_soon,
        "is_stale": is_stale,
        "urgency_score": round(urgency_score, 2),
    }


def _subcomponent_payload(
    subcomponent: Subcomponent,
    *,
    solution_repo_url: Optional[str] = None,
) -> dict:
    payload = SubcomponentRead.model_validate(subcomponent).model_dump(mode="json")
    effective_repo_url, repo_source = resolve_effective_github_repo_url(
        solution_repo_url=solution_repo_url,
        subcomponent_repo_url=subcomponent.github_repo_url,
    )
    payload["effective_github_repo_url"] = effective_repo_url
    payload["repo_source"] = repo_source
    payload.update(_subcomponent_actionability(subcomponent))
    return payload


def _publish_subcomponent_mutation(space_id: str) -> None:
    publish_space_mutation(
        space_id,
        ["subcomponents"],
        broadcast_channel="subcomponents",
    )


def _solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
    )


def _project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _subcomponent_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Subcomponent)
        .filter(Subcomponent.deleted_at.is_(None))
        .filter(Subcomponent.space_id == space_ctx.space_id)
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


def _get_subcomponent(session: Session, subcomponent_id: str, space_ctx: SpaceContext) -> Subcomponent:
    sc = (
        _subcomponent_query(session, space_ctx)
        .filter(Subcomponent.subcomponent_id == subcomponent_id)
        .first()
    )
    if not sc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subcomponent not found")
    return sc


@router.get(
    "/solutions/{solution_id}/subcomponents",
    response_model=List[SubcomponentRead],
)
def list_subcomponents(
    solution_id: str,
    status_filter: Optional[SubcomponentStatus] = Query(None, alias="status"),
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
    scope_token = make_scope_token("subcomponents", space_ctx.space_id)

    def _load():
        query = _subcomponent_query(session, space_ctx).filter(Subcomponent.solution_id == solution_id)
        if status_filter:
            query = query.filter(Subcomponent.status == status_filter)
        if priority is not None:
            query = query.filter(Subcomponent.priority == priority)
        if due_before:
            query = query.filter(Subcomponent.due_date <= due_before)
        if due_after:
            query = query.filter(Subcomponent.due_date >= due_after)
        if assignee_norm:
            query = query.filter(func.lower(Subcomponent.assignee) == assignee_norm)
        if assignee_user_soeid:
            query = query.filter(Subcomponent.assignee_user_soeid == assignee_user_soeid)
        rows = query.order_by(Subcomponent.priority.asc(), Subcomponent.created_at.asc()).all()
        solution_repo_map = _solution_repo_map(session, space_ctx, [solution_id])
        return [
            _subcomponent_payload(row, solution_repo_url=solution_repo_map.get(row.solution_id))
            for row in rows
        ]

    return cached_call(
        endpoint="subcomponents:list_by_solution",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_SUBCOMPONENTS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/subcomponents", response_model=List[SubcomponentRead])
def list_all_subcomponents(
    status_filter: Optional[SubcomponentStatus] = Query(None, alias="status"),
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
    scope_token = make_scope_token("subcomponents", space_ctx.space_id)

    def _load():
        query = _subcomponent_query(session, space_ctx)
        if status_filter:
            query = query.filter(Subcomponent.status == status_filter)
        if project_id:
            query = query.filter(Subcomponent.project_id == project_id)
        if solution_id:
            query = query.filter(Subcomponent.solution_id == solution_id)
        if priority is not None:
            query = query.filter(Subcomponent.priority == priority)
        if due_before:
            query = query.filter(Subcomponent.due_date <= due_before)
        if due_after:
            query = query.filter(Subcomponent.due_date >= due_after)
        if assignee_norm:
            query = query.filter(func.lower(Subcomponent.assignee) == assignee_norm)
        if assignee_user_soeid:
            query = query.filter(Subcomponent.assignee_user_soeid == assignee_user_soeid)
        rows = query.order_by(Subcomponent.priority.asc(), Subcomponent.created_at.asc()).all()
        solution_repo_map = _solution_repo_map(
            session, space_ctx, [row.solution_id for row in rows]
        )
        return [
            _subcomponent_payload(row, solution_repo_url=solution_repo_map.get(row.solution_id))
            for row in rows
        ]

    return cached_call(
        endpoint="subcomponents:list_all",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_SUBCOMPONENTS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post(
    "/solutions/{solution_id}/subcomponents",
    response_model=SubcomponentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_subcomponent(
    solution_id: str,
    payload: SubcomponentCreate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    solution = _ensure_solution(session, solution_id, space_ctx)
    try:
        github_repo_url = normalize_github_repo_url(payload.github_repo_url)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    conflict = (
        _subcomponent_query(session, space_ctx)
        .filter(Subcomponent.solution_id == solution_id)
        .filter(Subcomponent.subcomponent_name == payload.subcomponent_name)
        .first()
    )
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subcomponent name already exists in this solution",
        )

    now = datetime.now(timezone.utc)
    completed_at = now if payload.status == SubcomponentStatus.complete else None

    assignee = normalize_str(payload.assignee) or current_user.display_name or current_user.soeid or ""
    assignee_user_soeid = normalize_str(payload.assignee_user_soeid) or None
    if assignee_user_soeid is None and current_user.soeid:
        if assignee == current_user.display_name or assignee == current_user.soeid:
            assignee_user_soeid = current_user.soeid

    subcomponent = Subcomponent(
        space_id=space_ctx.space_id,
        project_id=solution.project_id,
        solution_id=solution_id,
        subcomponent_name=payload.subcomponent_name,
        status=payload.status,
        priority=payload.priority,
        due_date=payload.due_date,
        completed_at=completed_at,
        assignee=assignee,
        assignee_user_soeid=assignee_user_soeid,
        github_repo_url=github_repo_url,
        estimate_hours=payload.estimate_hours,
        blocked=payload.blocked or False,
        blocker_note=payload.blocker_note,
        done_criteria=payload.done_criteria,
        capacity_hours=payload.capacity_hours or 0,
        created_at=now,
        updated_at=now,
    )
    session.add(subcomponent)
    session.flush()
    log_changes(
        session,
        entity_type="subcomponent",
        entity_id=subcomponent.subcomponent_id,
        user_id=current_user.user_id,
        action="create",
        space_id=space_ctx.space_id,
        changes={
            "subcomponent_name": (None, subcomponent.subcomponent_name),
            "status": (None, subcomponent.status),
            "priority": (None, subcomponent.priority),
            "due_date": (None, subcomponent.due_date),
            "assignee": (None, subcomponent.assignee),
            "assignee_user_soeid": (None, subcomponent.assignee_user_soeid),
            "github_repo_url": (None, subcomponent.github_repo_url),
            "estimate_hours": (None, subcomponent.estimate_hours),
            "blocked": (None, subcomponent.blocked),
            "blocker_note": (None, subcomponent.blocker_note),
            "done_criteria": (None, subcomponent.done_criteria),
            "completed_at": (None, subcomponent.completed_at),
        },
    )
    commit_refresh_and_publish(
        session,
        subcomponent,
        space_id=space_ctx.space_id,
        cache_keys=["subcomponents"],
        broadcast_channel="subcomponents",
    )
    return _subcomponent_payload(subcomponent, solution_repo_url=solution.github_repo_url)


@router.post("/subcomponents/import")
def import_subcomponents(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {
            "created": 0,
            "updated": 0,
            "projects_created": 0,
            "solutions_created": 0,
            "errors": errors,
            "total_rows": 0,
        }
    created = updated = projects_created = solutions_created = 0
    seen = set()
    request_id = str(uuid4())

    projects_by_name = {p.project_name.lower(): p for p in _project_query(session, space_ctx).all()}
    solutions_by_key = {
        (s.project_id, s.solution_name.lower(), s.version.lower()): s
        for s in _solution_query(session, space_ctx).all()
    }

    for idx, row in enumerate(rows, start=2):
        project_name = normalize_str(row.get("project_name"))
        solution_name = normalize_str(row.get("solution_name"))
        sub_name = normalize_str(row.get("subcomponent_name"))
        version_raw = normalize_str(row.get("version")) or "0.1.0"
        solution_owner_val = normalize_str(row.get("solution_owner")) or normalize_str(row.get("owner"))
        assignee_val = normalize_str(row.get("assignee"))
        assignee_user_soeid = normalize_str(row.get("assignee_user_soeid")) or None
        blocker_note = normalize_str(row.get("blocker_note")) or None
        done_criteria = normalize_str(row.get("done_criteria")) or None
        try:
            github_repo_url = normalize_github_repo_url(row.get("github_repo_url"))
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue
        blocked_raw = normalize_str(row.get("blocked"))
        blocked_val = blocked_raw.lower() in {"true", "1", "yes", "y"} if blocked_raw else False
        if not project_name or not solution_name or not sub_name or not assignee_val:
            errors.append(
                f"Row {idx}: project_name, solution_name, subcomponent_name, and assignee are required"
            )
            continue
        key = (project_name.lower(), solution_name.lower(), version_raw.lower(), sub_name.lower())
        if key in seen:
            errors.append(
                f"Row {idx}: duplicate subcomponent '{sub_name}' for solution '{solution_name}' in project '{project_name}' (strict-first policy)"
            )
            continue
        seen.add(key)

        try:
            status_enum = normalize_status(
                row.get("status") or SubcomponentStatus.to_do.value, SubcomponentStatus
            )
            priority_val = parse_priority(row.get("priority"), default=3)
            due_val = parse_date(row.get("due_date"))
            estimate_hours = int(row.get("estimate_hours")) if normalize_str(row.get("estimate_hours")) else None
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue

        project = projects_by_name.get(project_name.lower())
        project_created_this_row = False
        if not project:
            sponsor_val = solution_owner_val or "Auto-created"
            project = Project(
                space_id=space_ctx.space_id,
                project_name=project_name,
                status=ProjectStatus.not_started,
                description=None,
                sponsor=sponsor_val,
            )
            session.add(project)
            session.flush()  # ensure project_id available
            project_created_this_row = True
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
                    "sponsor": (None, project.sponsor),
                },
                request_id=request_id,
            )

        solution_key = (project.project_id, solution_name.lower(), version_raw.lower())
        solution = solutions_by_key.get(solution_key)
        solution_created_this_row = False
        if not solution:
            try:
                solution = Solution(
                    space_id=space_ctx.space_id,
                    project_id=project.project_id,
                    solution_name=solution_name,
                    version=version_raw,
                    status=SolutionStatus.not_started,
                    priority=3,
                    due_date=None,
                    current_phase=None,
                    description=None,
                    owner=solution_owner_val or "Auto-created",
                    assignee="",
                    approver=None,
                    key_stakeholder=None,
                    blockers=None,
                    risks=None,
                    completed_at=None,
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
                        "owner": (None, solution.owner),
                        "assignee": (None, solution.assignee),
                        "approver": (None, solution.approver),
                        "key_stakeholder": (None, solution.key_stakeholder),
                        "blockers": (None, solution.blockers),
                        "risks": (None, solution.risks),
                        "completed_at": (None, solution.completed_at),
                    },
                    request_id=request_id,
                )
                enable_all_phases(session, solution.solution_id)
                solution_created_this_row = True
            except Exception as exc:
                session.rollback()
                errors.append(f"Row {idx}: {exc}")
                continue

        try:
            existing = (
                _subcomponent_query(session, space_ctx)
                .filter(Subcomponent.solution_id == solution.solution_id)
                .filter(Subcomponent.subcomponent_name == sub_name)
                .first()
            )
            now = datetime.now(timezone.utc)
            if existing:
                before = {
                    "status": existing.status,
                    "priority": existing.priority,
                    "due_date": existing.due_date,
                    "assignee": existing.assignee,
                    "assignee_user_soeid": existing.assignee_user_soeid,
                    "github_repo_url": existing.github_repo_url,
                    "estimate_hours": existing.estimate_hours,
                    "blocked": existing.blocked,
                    "blocker_note": existing.blocker_note,
                    "done_criteria": existing.done_criteria,
                    "completed_at": existing.completed_at,
                }
                existing.status = status_enum
                existing.priority = priority_val
                existing.due_date = due_val
                existing.assignee = assignee_val
                existing.assignee_user_soeid = assignee_user_soeid
                existing.github_repo_url = github_repo_url
                existing.estimate_hours = estimate_hours
                existing.blocked = blocked_val
                existing.blocker_note = blocker_note
                existing.done_criteria = done_criteria
                existing.updated_at = now
                if not existing.space_id:
                    existing.space_id = space_ctx.space_id
                if status_enum == SubcomponentStatus.complete and not existing.completed_at:
                    existing.completed_at = now
                session.add(existing)
                log_changes(
                    session,
                    entity_type="subcomponent",
                    entity_id=existing.subcomponent_id,
                    user_id=current_user.user_id,
                    action="update",
                    space_id=space_ctx.space_id,
                    changes={
                        "status": (before["status"], existing.status),
                        "priority": (before["priority"], existing.priority),
                        "due_date": (before["due_date"], existing.due_date),
                        "assignee": (before["assignee"], existing.assignee),
                        "assignee_user_soeid": (before["assignee_user_soeid"], existing.assignee_user_soeid),
                        "github_repo_url": (before["github_repo_url"], existing.github_repo_url),
                        "estimate_hours": (before["estimate_hours"], existing.estimate_hours),
                        "blocked": (before["blocked"], existing.blocked),
                        "blocker_note": (before["blocker_note"], existing.blocker_note),
                        "done_criteria": (before["done_criteria"], existing.done_criteria),
                        "completed_at": (before["completed_at"], existing.completed_at),
                    },
                    request_id=request_id,
                )
                commit_session(session)
                updated += 1
            else:
                completed_at = now if status_enum == SubcomponentStatus.complete else None
                subcomponent = Subcomponent(
                    space_id=space_ctx.space_id,
                    project_id=project.project_id,
                    solution_id=solution.solution_id,
                    subcomponent_name=sub_name,
                    status=status_enum,
                    priority=priority_val,
                    due_date=due_val,
                    assignee=assignee_val,
                    assignee_user_soeid=assignee_user_soeid,
                    github_repo_url=github_repo_url,
                    estimate_hours=estimate_hours,
                    blocked=blocked_val,
                    blocker_note=blocker_note,
                    done_criteria=done_criteria,
                    completed_at=completed_at,
                )
                session.add(subcomponent)
                session.flush()
                log_changes(
                    session,
                    entity_type="subcomponent",
                    entity_id=subcomponent.subcomponent_id,
                    user_id=current_user.user_id,
                    action="create",
                    space_id=space_ctx.space_id,
                    changes={
                        "subcomponent_name": (None, subcomponent.subcomponent_name),
                        "status": (None, subcomponent.status),
                        "priority": (None, subcomponent.priority),
                        "due_date": (None, subcomponent.due_date),
                        "assignee": (None, subcomponent.assignee),
                        "assignee_user_soeid": (None, subcomponent.assignee_user_soeid),
                        "github_repo_url": (None, subcomponent.github_repo_url),
                        "estimate_hours": (None, subcomponent.estimate_hours),
                        "blocked": (None, subcomponent.blocked),
                        "blocker_note": (None, subcomponent.blocker_note),
                        "done_criteria": (None, subcomponent.done_criteria),
                        "completed_at": (None, subcomponent.completed_at),
                    },
                    request_id=request_id,
                )
                commit_session(session)
                created += 1
            if project_created_this_row:
                projects_by_name[project_name.lower()] = project
                projects_created += 1
            if solution_created_this_row:
                solutions_by_key[solution_key] = solution
                solutions_created += 1
        except ValueError as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")
        except Exception as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")

    _publish_subcomponent_mutation(space_ctx.space_id)
    return {
        "created": created,
        "updated": updated,
        "projects_created": projects_created,
        "solutions_created": solutions_created,
        "errors": errors,
        "total_rows": len(rows),
    }


@router.get("/subcomponents/export")
def export_subcomponents(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    subs = _subcomponent_query(session, space_ctx).order_by(Subcomponent.created_at.asc()).all()
    project_map = {p.project_id: p.project_name for p in _project_query(session, space_ctx)}
    solution_map = {
        s.solution_id: (s.solution_name, s.version)
        for s in _solution_query(session, space_ctx)
    }
    buffer = StringIO()
    fieldnames = [
        "project_name",
        "solution_name",
        "version",
        "subcomponent_name",
        "status",
        "priority",
        "due_date",
        "assignee",
        "assignee_user_soeid",
        "github_repo_url",
        "estimate_hours",
        "blocked",
        "blocker_note",
        "done_criteria",
        "completed_at",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for sc in subs:
        sol_name, sol_version = solution_map.get(sc.solution_id, ("", ""))
        writer.writerow(
            {
                "project_name": project_map.get(sc.project_id, ""),
                "solution_name": sol_name,
                "version": sol_version,
                "subcomponent_name": sc.subcomponent_name,
                "status": sc.status.value if hasattr(sc.status, "value") else sc.status,
                "priority": sc.priority,
                "due_date": sc.due_date.isoformat() if sc.due_date else "",
                "assignee": sc.assignee or "",
                "assignee_user_soeid": sc.assignee_user_soeid or "",
                "github_repo_url": sc.github_repo_url or "",
                "estimate_hours": sc.estimate_hours if sc.estimate_hours is not None else "",
                "blocked": sc.blocked,
                "blocker_note": sc.blocker_note or "",
                "done_criteria": sc.done_criteria or "",
                "completed_at": sc.completed_at.isoformat() if sc.completed_at else "",
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="subcomponents.csv"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)


@router.get("/subcomponents/{subcomponent_id}", response_model=SubcomponentRead)
def get_subcomponent(
    subcomponent_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    scope_token = make_scope_token("subcomponents", space_ctx.space_id)

    def _load():
        subcomponent = _get_subcomponent(session, subcomponent_id, space_ctx)
        solution = _ensure_solution(session, subcomponent.solution_id, space_ctx)
        return _subcomponent_payload(subcomponent, solution_repo_url=solution.github_repo_url)

    return cached_call(
        endpoint="subcomponents:detail",
        params={"subcomponent_id": subcomponent_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_SUBCOMPONENTS_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/subcomponents/{subcomponent_id}/activity", response_model=List[ChangeLogRead])
def list_subcomponent_activity(
    subcomponent_id: str,
    limit: int = Query(20, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    _get_subcomponent(session, subcomponent_id, space_ctx)
    rows = (
        session.query(ChangeLog)
        .filter(ChangeLog.space_id == space_ctx.space_id)
        .filter(ChangeLog.entity_type == "subcomponent")
        .filter(ChangeLog.entity_id == subcomponent_id)
        .order_by(ChangeLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return rows


@router.patch("/subcomponents/{subcomponent_id}", response_model=SubcomponentRead)
def update_subcomponent(
    subcomponent_id: str,
    payload: SubcomponentUpdate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    subcomponent = _get_subcomponent(session, subcomponent_id, space_ctx)

    update_data = payload.model_dump(exclude_unset=True)
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "blocked" in update_data and update_data["blocked"] is None:
        update_data["blocked"] = False
    if "github_repo_url" in update_data:
        try:
            update_data["github_repo_url"] = normalize_github_repo_url(update_data["github_repo_url"])
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    before = {field: getattr(subcomponent, field) for field in update_data.keys()}
    for field, value in update_data.items():
        setattr(subcomponent, field, value)

    if "status" in update_data and update_data["status"] == SubcomponentStatus.complete:
        subcomponent.completed_at = subcomponent.completed_at or datetime.now(timezone.utc)

    subcomponent.updated_at = datetime.now(timezone.utc)

    if "subcomponent_name" in update_data and update_data["subcomponent_name"]:
        conflict = (
            _subcomponent_query(session, space_ctx)
            .filter(Subcomponent.solution_id == subcomponent.solution_id)
            .filter(Subcomponent.subcomponent_name == update_data["subcomponent_name"])
            .filter(Subcomponent.subcomponent_id != subcomponent.subcomponent_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subcomponent name already exists in this solution",
            )

    session.add(subcomponent)
    if update_data:
        log_changes(
            session,
            entity_type="subcomponent",
            entity_id=subcomponent.subcomponent_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes={field: (before.get(field), getattr(subcomponent, field)) for field in update_data.keys()},
        )
    commit_refresh_and_publish(
        session,
        subcomponent,
        space_id=space_ctx.space_id,
        cache_keys=["subcomponents"],
        broadcast_channel="subcomponents",
    )
    solution = _ensure_solution(session, subcomponent.solution_id, space_ctx)
    return _subcomponent_payload(subcomponent, solution_repo_url=solution.github_repo_url)


@router.patch("/subcomponents/actions/batch", response_model=List[SubcomponentRead])
def batch_update_subcomponents(
    payload: SubcomponentBatchUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    unique_ids: list[str] = []
    seen: set[str] = set()
    for raw_id in payload.subcomponent_ids or []:
        sub_id = (raw_id or "").strip()
        if not sub_id or sub_id in seen:
            continue
        seen.add(sub_id)
        unique_ids.append(sub_id)
    if not unique_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="subcomponent_ids must include at least one item",
        )
    if payload.due_date is not None and payload.due_date_shift_days is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either due_date or due_date_shift_days, not both",
        )

    rows = (
        _subcomponent_query(session, space_ctx)
        .filter(Subcomponent.subcomponent_id.in_(unique_ids))
        .all()
    )
    rows_by_id = {row.subcomponent_id: row for row in rows}
    missing = [sub_id for sub_id in unique_ids if sub_id not in rows_by_id]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subcomponents not found in current space: {', '.join(missing)}",
        )

    now = datetime.now(timezone.utc)
    updated_rows: list[Subcomponent] = []
    for sub_id in unique_ids:
        row = rows_by_id[sub_id]
        changes = {}

        def track(field: str, value):
            old = getattr(row, field)
            if old != value:
                setattr(row, field, value)
                changes[field] = (old, value)

        if payload.status is not None:
            track("status", payload.status)
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

        if changes.get("status", (None, None))[1] == SubcomponentStatus.complete and not row.completed_at:
            track("completed_at", now)

        if not changes:
            updated_rows.append(row)
            continue

        track("updated_at", now)
        session.add(row)
        log_changes(
            session,
            entity_type="subcomponent",
            entity_id=row.subcomponent_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes=changes,
        )
        updated_rows.append(row)

    commit_session(session)
    for row in updated_rows:
        session.refresh(row)
    _publish_subcomponent_mutation(space_ctx.space_id)
    return [_subcomponent_payload(row) for row in updated_rows]


@router.delete("/subcomponents/{subcomponent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subcomponent(
    subcomponent_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    subcomponent = _get_subcomponent(session, subcomponent_id, space_ctx)
    now = datetime.now(timezone.utc)
    subcomponent.deleted_at = now
    subcomponent.updated_at = now
    session.add(subcomponent)
    log_changes(
        session,
        entity_type="subcomponent",
        entity_id=subcomponent.subcomponent_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    commit_session(session)
    _publish_subcomponent_mutation(space_ctx.space_id)
    return None

