from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..models import ResourceAllocation, Team, PlanningWindow, User
from ..schemas import (
    ResourceAllocationCreate,
    ResourceAllocationRead,
    ResourceAllocationUpdate,
    PlanningWindowCreate,
    PlanningWindowRead,
    PlanningWindowUpdate,
)
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token

router = APIRouter()
_PLANNING_LIST_TTL_SECONDS = 20
_PLANNING_DETAIL_TTL_SECONDS = 30
_HOURS_PER_FTE_MONTH = 160.0


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _allocation_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(ResourceAllocation)
        .filter(ResourceAllocation.deleted_at.is_(None))
        .filter(ResourceAllocation.space_id == space_ctx.space_id)
    )


def _window_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(PlanningWindow)
        .filter(PlanningWindow.deleted_at.is_(None))
        .filter(PlanningWindow.space_id == space_ctx.space_id)
    )


def _active_team(session: Session, team_id: Optional[str], space_ctx: SpaceContext) -> None:
    if not team_id:
        return
    exists = (
        session.query(Team)
        .filter(Team.team_id == team_id)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
        .first()
    )
    if not exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")


def _get_allocation(session: Session, alloc_id: str, space_ctx: SpaceContext) -> ResourceAllocation:
    alloc = (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.allocation_id == alloc_id)
        .first()
    )
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    return alloc


def _get_window(session: Session, window_id: str, space_ctx: SpaceContext) -> PlanningWindow:
    win = (
        _window_query(session, space_ctx)
        .filter(PlanningWindow.window_id == window_id)
        .first()
    )
    if not win:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planning window not found")
    return win


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _resolve_month_start(month_start: Optional[date], week_start: Optional[date]) -> date:
    raw = month_start or week_start
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month_start (or legacy week_start) is required",
        )
    return _month_start(raw)


def _resolve_fte_months(fte_months: Optional[float], hours: Optional[int]) -> float:
    if fte_months is not None:
        return round(max(float(fte_months), 0.0), 3)
    if hours is not None:
        return round(max(float(hours), 0.0) / _HOURS_PER_FTE_MONTH, 3)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="fte_months (or legacy hours) is required",
    )


def _hours_from_fte_months(value: float) -> int:
    return max(int(round(float(value) * _HOURS_PER_FTE_MONTH)), 0)


def _allocation_month_expr():
    return func.coalesce(ResourceAllocation.month_start, ResourceAllocation.week_start)


def _allocation_fte_expr():
    return func.coalesce(ResourceAllocation.fte_months, (ResourceAllocation.hours / _HOURS_PER_FTE_MONTH))


def _allocation_to_payload(alloc: ResourceAllocation) -> dict:
    month_start = alloc.month_start or (_month_start(alloc.week_start) if alloc.week_start else None)
    week_start = alloc.week_start or month_start
    fte_months = float(alloc.fte_months or 0.0)
    if fte_months <= 0 and alloc.hours:
        fte_months = round(float(alloc.hours) / _HOURS_PER_FTE_MONTH, 3)
    hours = alloc.hours if alloc.hours is not None else _hours_from_fte_months(fte_months)
    return {
        "allocation_id": alloc.allocation_id,
        "work_item_type": alloc.work_item_type,
        "work_item_id": alloc.work_item_id,
        "assignee": alloc.assignee,
        "assignee_user_soeid": alloc.assignee_user_soeid,
        "team_id": alloc.team_id,
        "month_start": month_start.isoformat() if month_start else None,
        "fte_months": round(fte_months, 3),
        "week_start": week_start.isoformat() if week_start else None,
        "hours": int(hours or 0),
        "window_id": alloc.window_id,
        "created_at": alloc.created_at,
        "updated_at": alloc.updated_at,
    }


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
        month_expr = _allocation_month_expr()
        query = _allocation_query(session, space_ctx)
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
        return [_allocation_to_payload(row) for row in rows]

    return cached_call(
        endpoint="planning:allocations:list",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
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
    _active_team(session, payload.team_id, space_ctx)
    if payload.window_id:
        _get_window(session, payload.window_id, space_ctx)
    month_start = _resolve_month_start(payload.month_start, payload.week_start)
    fte_months = _resolve_fte_months(payload.fte_months, payload.hours)
    alloc = ResourceAllocation(
        space_id=space_ctx.space_id,
        work_item_type=payload.work_item_type,
        work_item_id=payload.work_item_id,
        assignee_user_soeid=payload.assignee_user_soeid or payload.assignee,
        assignee=payload.assignee,
        team_id=payload.team_id,
        week_start=payload.week_start or month_start,
        month_start=month_start,
        hours=_hours_from_fte_months(fte_months),
        fte_months=fte_months,
        window_id=payload.window_id,
    )
    session.add(alloc)
    session.commit()
    session.refresh(alloc)
    invalidate_space(space_ctx.space_id, ["planning"])
    return ResourceAllocationRead.model_validate(_allocation_to_payload(alloc))


@router.patch("/resource-allocations/{allocation_id}", response_model=ResourceAllocationRead)
def update_allocation(
    allocation_id: str,
    payload: ResourceAllocationUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> ResourceAllocationRead:
    alloc = _get_allocation(session, allocation_id, space_ctx)
    if payload.team_id is not None:
        _active_team(session, payload.team_id, space_ctx)
    if payload.window_id:
        _get_window(session, payload.window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field in ["work_item_type", "work_item_id", "assignee", "assignee_user_soeid", "team_id", "window_id"]:
        if field in update_data:
            setattr(alloc, field, update_data[field])

    month_start_set = False
    if "month_start" in update_data and update_data["month_start"] is not None:
        alloc.month_start = _month_start(update_data["month_start"])
        month_start_set = True
        if "week_start" not in update_data:
            alloc.week_start = alloc.month_start
    if "week_start" in update_data and update_data["week_start"] is not None:
        alloc.week_start = update_data["week_start"]
        if not month_start_set:
            alloc.month_start = _month_start(update_data["week_start"])

    if "fte_months" in update_data and update_data["fte_months"] is not None:
        alloc.fte_months = round(max(float(update_data["fte_months"]), 0.0), 3)
        alloc.hours = _hours_from_fte_months(alloc.fte_months)
    elif "hours" in update_data and update_data["hours"] is not None:
        alloc.hours = max(int(update_data["hours"]), 0)
        alloc.fte_months = round(float(alloc.hours) / _HOURS_PER_FTE_MONTH, 3)

    if alloc.month_start is None and alloc.week_start is not None:
        alloc.month_start = _month_start(alloc.week_start)
    if alloc.week_start is None and alloc.month_start is not None:
        alloc.week_start = alloc.month_start

    alloc.updated_at = datetime.now(timezone.utc)
    session.add(alloc)
    session.commit()
    session.refresh(alloc)
    invalidate_space(space_ctx.space_id, ["planning"])
    return ResourceAllocationRead.model_validate(_allocation_to_payload(alloc))


@router.delete("/resource-allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    alloc = _get_allocation(session, allocation_id, space_ctx)
    alloc.deleted_at = datetime.now(timezone.utc)
    session.add(alloc)
    session.commit()
    invalidate_space(space_ctx.space_id, ["planning"])
    return None


@router.get("/resource-allocations/summary")
def allocations_summary(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    window_id: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    params = {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "window_id": window_id,
    }
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        month_expr = _allocation_month_expr()
        fte_expr = _allocation_fte_expr()
        query = session.query(
            ResourceAllocation.assignee_user_soeid,
            func.min(ResourceAllocation.assignee).label("assignee"),
            month_expr.label("month_start"),
            func.sum(fte_expr).label("fte_months"),
        ).filter(ResourceAllocation.deleted_at.is_(None)).filter(ResourceAllocation.space_id == space_ctx.space_id)
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
                "assignee_user_soeid": r.assignee_user_soeid,
                "assignee": r.assignee,
                "month_start": str(r.month_start) if r.month_start else None,
                "week_start": str(r.month_start) if r.month_start else None,
                "fte_months": round(float(r.fte_months or 0), 3),
                "hours": _hours_from_fte_months(float(r.fte_months or 0)),
            }
            for r in rows
        ]

    return cached_call(
        endpoint="planning:allocations:summary",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PLANNING_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


# Planning windows
@router.get("/planning/windows", response_model=List[PlanningWindowRead])
def list_windows(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[PlanningWindowRead]:
    scope_token = make_scope_token("planning", space_ctx.space_id)

    def _load():
        wins = (
            _window_query(session, space_ctx)
            .order_by(PlanningWindow.start_date.asc())
            .all()
        )
        return [PlanningWindowRead.model_validate(w).model_dump(mode="json") for w in wins]

    return cached_call(
        endpoint="planning:windows:list",
        params={},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
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
    session.commit()
    session.refresh(win)
    invalidate_space(space_ctx.space_id, ["planning"])
    return PlanningWindowRead.model_validate(win)


@router.patch("/planning/windows/{window_id}", response_model=PlanningWindowRead)
def update_window(
    window_id: str,
    payload: PlanningWindowUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> PlanningWindowRead:
    win = _get_window(session, window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(win, field, val)
    win.updated_at = datetime.now(timezone.utc)
    session.add(win)
    session.commit()
    session.refresh(win)
    invalidate_space(space_ctx.space_id, ["planning"])
    return PlanningWindowRead.model_validate(win)


@router.delete("/planning/windows/{window_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_window(
    window_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    win = _get_window(session, window_id, space_ctx)
    win.deleted_at = datetime.now(timezone.utc)
    session.add(win)
    session.commit()
    invalidate_space(space_ctx.space_id, ["planning"])
    return None
