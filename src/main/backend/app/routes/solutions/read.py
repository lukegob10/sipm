from __future__ import annotations

from datetime import date
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db
from ...models import Solution, User
from ...schemas import SolutionRead
from ...services.smart_cache import cached_call, make_scope_token
from ...services.spaces import SpaceContext
from .common import (
    _SOLUTIONS_DETAIL_TTL_SECONDS,
    _SOLUTIONS_LIST_TTL_SECONDS,
    _ensure_project_exists,
    _exclude_work_allocation_board_solutions,
    _get_solution_or_404,
    _role_scope,
    _solution_payload,
    _solution_query,
)
from ...utils.enums import SolutionStatus

router = APIRouter()


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
        query = _exclude_work_allocation_board_solutions(_solution_query(session, space_ctx), session, space_ctx)
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
        query = _exclude_work_allocation_board_solutions(_solution_query(session, space_ctx), session, space_ctx)
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
