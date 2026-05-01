from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ...models import PlanningWindow, ResourceAllocation, User
from ...schemas import (
    PlanningWindowCreate,
    PlanningWindowRead,
    PlanningWindowUpdate,
    ResourceAllocationCreate,
    ResourceAllocationRead,
    ResourceAllocationUpdate,
)
from ...services.smart_cache import cached_call, make_scope_token
from ...services.spaces import SpaceContext
from .common import (
    _HOURS_PER_FTE_MONTH,
    _PLANNING_DETAIL_TTL_SECONDS,
    _PLANNING_LIST_TTL_SECONDS,
    allocation_fte_expr,
    allocation_month_expr,
    allocation_query,
    allocation_to_payload,
    commit_planning_mutation,
    get_allocation,
    get_window,
    hours_from_fte_months,
    month_start,
    resolve_fte_months,
    resolve_month_start,
    role_scope,
    window_query,
    active_team,
    raise_window_name_conflict,
)


router = APIRouter()


@router.get("/resource-allocations", response_model=List[ResourceAllocationRead])
def list_allocations(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    assignee: Optional[str] = None,
    assignee_user_soeid: Optional[str] = None,
    team_id: Optional[str] = None,
    window_id: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    assignee_norm = assignee.strip().lower() if assignee else None
    params = {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "assignee": assignee_norm,
        "assignee_user_soeid": assignee_user_soeid,
        "team_id": team_id,
        "window_id": window_id,
    }
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        month_expr = allocation_month_expr()
        query = allocation_query(session, space_ctx)
        if from_date:
            query = query.filter(month_expr >= from_date)
        if to_date:
            query = query.filter(month_expr <= to_date)
        if assignee_norm:
            query = query.filter(func.lower(ResourceAllocation.assignee) == assignee_norm)
        if assignee_user_soeid:
            query = query.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
        if team_id:
            query = query.filter(ResourceAllocation.team_id == team_id)
        if window_id:
            query = query.filter(ResourceAllocation.window_id == window_id)
        rows = query.order_by(month_expr.asc(), ResourceAllocation.assignee_user_soeid.asc()).all()
        return [allocation_to_payload(row) for row in rows]

    return cached_call(
        endpoint="planning:allocations:list",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=role_scope(space_ctx),
        ttl_seconds=_PLANNING_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/resource-allocations", response_model=ResourceAllocationRead, status_code=status.HTTP_201_CREATED)
def create_allocation(
    payload: ResourceAllocationCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> ResourceAllocationRead:
    active_team(session, payload.team_id, space_ctx)
    if payload.window_id:
        get_window(session, payload.window_id, space_ctx)
    normalized_month_start = resolve_month_start(payload.month_start, payload.week_start)
    fte_months = resolve_fte_months(payload.fte_months, payload.hours)
    alloc = ResourceAllocation(
        space_id=space_ctx.space_id,
        work_item_type=payload.work_item_type,
        work_item_id=payload.work_item_id,
        assignee_user_soeid=payload.assignee_user_soeid,
        assignee=payload.assignee,
        team_id=payload.team_id,
        week_start=payload.week_start or normalized_month_start,
        month_start=normalized_month_start,
        hours=hours_from_fte_months(fte_months),
        fte_months=fte_months,
        window_id=payload.window_id,
    )
    session.add(alloc)
    commit_planning_mutation(session, space_ctx, refresh=alloc)
    return ResourceAllocationRead.model_validate(allocation_to_payload(alloc))


@router.patch("/resource-allocations/{allocation_id}", response_model=ResourceAllocationRead)
def update_allocation(
    allocation_id: str,
    payload: ResourceAllocationUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> ResourceAllocationRead:
    alloc = get_allocation(session, allocation_id, space_ctx)
    if payload.team_id is not None:
        active_team(session, payload.team_id, space_ctx)
    if payload.window_id:
        get_window(session, payload.window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field in ["work_item_type", "work_item_id", "assignee", "assignee_user_soeid", "team_id", "window_id"]:
        if field in update_data:
            setattr(alloc, field, update_data[field])

    month_start_set = False
    if "month_start" in update_data and update_data["month_start"] is not None:
        alloc.month_start = month_start(update_data["month_start"])
        month_start_set = True
        if "week_start" not in update_data:
            alloc.week_start = alloc.month_start
    if "week_start" in update_data and update_data["week_start"] is not None:
        alloc.week_start = update_data["week_start"]
        if not month_start_set:
            alloc.month_start = month_start(update_data["week_start"])

    if "fte_months" in update_data and update_data["fte_months"] is not None:
        alloc.fte_months = round(max(float(update_data["fte_months"]), 0.0), 3)
        alloc.hours = hours_from_fte_months(alloc.fte_months)
    elif "hours" in update_data and update_data["hours"] is not None:
        alloc.hours = max(int(update_data["hours"]), 0)
        alloc.fte_months = round(float(alloc.hours) / _HOURS_PER_FTE_MONTH, 3)

    if alloc.month_start is None and alloc.week_start is not None:
        alloc.month_start = month_start(alloc.week_start)
    if alloc.week_start is None and alloc.month_start is not None:
        alloc.week_start = alloc.month_start

    alloc.updated_at = datetime.now(timezone.utc)
    session.add(alloc)
    commit_planning_mutation(session, space_ctx, refresh=alloc)
    return ResourceAllocationRead.model_validate(allocation_to_payload(alloc))


@router.delete("/resource-allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    alloc = get_allocation(session, allocation_id, space_ctx)
    alloc.deleted_at = datetime.now(timezone.utc)
    session.add(alloc)
    commit_planning_mutation(session, space_ctx)
    return None


@router.get("/resource-allocations/summary")
def allocations_summary(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    window_id: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    params = {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "window_id": window_id,
    }
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        month_expr = allocation_month_expr()
        fte_expr = allocation_fte_expr()
        query = (
            session.query(
                ResourceAllocation.assignee_user_soeid,
                func.min(ResourceAllocation.assignee).label("assignee"),
                month_expr.label("month_start"),
                func.sum(fte_expr).label("fte_months"),
            )
            .filter(ResourceAllocation.deleted_at.is_(None))
            .filter(ResourceAllocation.space_id == space_ctx.space_id)
        )
        if from_date:
            query = query.filter(month_expr >= from_date)
        if to_date:
            query = query.filter(month_expr <= to_date)
        if window_id:
            query = query.filter(ResourceAllocation.window_id == window_id)
        rows = (
            query.group_by(ResourceAllocation.assignee_user_soeid, month_expr)
            .order_by(month_expr.asc(), ResourceAllocation.assignee_user_soeid.asc())
            .all()
        )
        return [
            {
                "assignee_user_soeid": row.assignee_user_soeid,
                "assignee": row.assignee,
                "month_start": str(row.month_start) if row.month_start else None,
                "week_start": str(row.month_start) if row.month_start else None,
                "fte_months": round(float(row.fte_months or 0), 3),
                "hours": hours_from_fte_months(float(row.fte_months or 0)),
            }
            for row in rows
        ]

    return cached_call(
        endpoint="planning:allocations:summary",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=role_scope(space_ctx),
        ttl_seconds=_PLANNING_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.get("/planning/windows", response_model=List[PlanningWindowRead])
def list_windows(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[PlanningWindowRead]:
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        wins = window_query(session, space_ctx).order_by(PlanningWindow.start_date.asc()).all()
        return [PlanningWindowRead.model_validate(win).model_dump(mode="json") for win in wins]

    return cached_call(
        endpoint="planning:windows:list",
        params={},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=role_scope(space_ctx),
        ttl_seconds=_PLANNING_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/planning/windows", response_model=PlanningWindowRead, status_code=status.HTTP_201_CREATED)
def create_window(
    payload: PlanningWindowCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> PlanningWindowRead:
    win = PlanningWindow(
        space_id=space_ctx.space_id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    session.add(win)
    commit_planning_mutation(
        session,
        space_ctx,
        refresh=win,
        on_integrity_error=raise_window_name_conflict,
    )
    return PlanningWindowRead.model_validate(win)


@router.patch("/planning/windows/{window_id}", response_model=PlanningWindowRead)
def update_window(
    window_id: str,
    payload: PlanningWindowUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> PlanningWindowRead:
    win = get_window(session, window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(win, field, val)
    win.updated_at = datetime.now(timezone.utc)
    session.add(win)
    commit_planning_mutation(
        session,
        space_ctx,
        refresh=win,
        on_integrity_error=raise_window_name_conflict,
    )
    return PlanningWindowRead.model_validate(win)


@router.delete("/planning/windows/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_window(
    window_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    win = get_window(session, window_id, space_ctx)
    win.deleted_at = datetime.now(timezone.utc)
    session.add(win)
    commit_planning_mutation(session, space_ctx)
    return None
