from datetime import date, datetime, timezone
from io import BytesIO
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth.auth import hash_bootstrap_password
from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..models import (
    PlanningWindow,
    ResourceAllocation,
    SpaceMembership,
    Subcomponent,
    Team,
    User,
)
from ..schemas import (
    ResourceAllocationCreate,
    ResourceAllocationRead,
    ResourceAllocationUpdate,
    PlanningWindowCreate,
    PlanningWindowRead,
    PlanningWindowUpdate,
)
from ..services.planning_report_pdf import build_work_allocation_report_pdf
from ..services.planning_work_allocation import (
    WORK_ALLOCATION_DEFAULT_ASSIGNEE,
    WORK_ALLOCATION_DOMAIN,
    active_person_by_soeid,
    active_space_user_query,
    board_solution,
    ensure_membership,
    month_from_token,
    month_token,
    next_available_soeid,
    planning_task_query,
    task_fte_months,
    team_display_name,
    team_name_to_id_map,
)
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, make_scope_token
from ..utils.enums import SubcomponentStatus
from ._mutations import commit_refresh_and_publish, commit_session, publish_space_mutation

router = APIRouter()
_PLANNING_LIST_TTL_SECONDS = 20
_PLANNING_DETAIL_TTL_SECONDS = 30
_HOURS_PER_FTE_MONTH = 160.0

_WORK_ALLOCATION_UNIQUE_CONSTRAINT = "UIX_ALLOC_UNIQUE_ASSIGNMENT"


class WorkAllocationTeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)


class WorkAllocationTeamUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)


class WorkAllocationTeamRead(BaseModel):
    id: str
    name: str


class WorkAllocationPersonCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    team_id: Optional[str] = None
    capacity_fte_months: float = 1.0


class WorkAllocationPersonUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=180)
    team_id: Optional[str] = None
    capacity_fte_months: Optional[float] = None
    active: Optional[bool] = None


class WorkAllocationPersonRead(BaseModel):
    id: str
    name: str
    team_id: Optional[str] = None
    capacity_fte_months: float
    active: bool


class WorkAllocationTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    fte_months: float = 0.25


class WorkAllocationTaskUpdate(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=240)
    fte_months: Optional[float] = None


class WorkAllocationTaskRead(BaseModel):
    id: str
    title: str
    fte_months: float
    status: Literal["backlog", "assigned"]


class WorkAllocationAssignmentCreate(BaseModel):
    task_id: str = Field(min_length=1)
    assignee_type: Literal["person", "team"]
    assignee_id: str = Field(min_length=1)
    month: str = Field(min_length=7, max_length=7)
    fte_months_allocated: Optional[float] = None


class WorkAllocationAssignmentUpdate(BaseModel):
    assignee_type: Literal["person", "team"]
    assignee_id: str = Field(min_length=1)
    fte_months_allocated: Optional[float] = None


class WorkAllocationAssignmentRead(BaseModel):
    id: str
    task_id: str
    assignee_type: Literal["person", "team"]
    assignee_id: str
    assignee_name: Optional[str] = None
    month: str
    fte_months_allocated: float


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _commit_planning_mutation(
    session: Session,
    space_ctx: SpaceContext,
    *,
    cache_keys: tuple[str, ...] = ("planning",),
    refresh: object | None = None,
    on_integrity_error=None,
) -> None:
    if refresh is None:
        commit_session(session, on_integrity_error=on_integrity_error)
        publish_space_mutation(space_ctx.space_id, cache_keys)
        return
    commit_refresh_and_publish(
        session,
        refresh,
        space_id=space_ctx.space_id,
        cache_keys=cache_keys,
        on_integrity_error=on_integrity_error,
    )


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


def _team_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
    )


def _active_team(session: Session, team_id: Optional[str], space_ctx: SpaceContext) -> Optional[Team]:
    if not team_id:
        return None
    row = _team_query(session, space_ctx).filter(Team.team_id == team_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return row


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


def _person_payload(user: User, team_map: dict[str, str]) -> WorkAllocationPersonRead:
    team_key = str(user.team_tag or "").strip().lower()
    team_id = team_map.get(team_key) if team_key else None
    cap = user.capacity_fte_month
    if cap is None or cap < 0:
        cap = 1.0
    return WorkAllocationPersonRead(
        id=user.soeid,
        name=user.display_name,
        team_id=team_id,
        capacity_fte_months=round(float(cap), 3),
        active=bool(user.is_active),
    )


def _task_payload(subcomponent: Subcomponent, assigned_ids: set[str]) -> WorkAllocationTaskRead:
    return WorkAllocationTaskRead(
        id=subcomponent.subcomponent_id,
        title=subcomponent.subcomponent_name,
        fte_months=task_fte_months(
            subcomponent,
            hours_per_fte_month=_HOURS_PER_FTE_MONTH,
        ),
        status="assigned" if subcomponent.subcomponent_id in assigned_ids else "backlog",
    )


def _allocation_for_board_payload(alloc: ResourceAllocation, space_ctx: SpaceContext, session: Session) -> WorkAllocationAssignmentRead:
    month_value = alloc.month_start or alloc.week_start
    fte = float(alloc.fte_months or 0.0)
    if fte <= 0 and alloc.hours:
        fte = float(alloc.hours) / _HOURS_PER_FTE_MONTH
    assignee_type: Literal["person", "team"] = "team" if alloc.team_id else "person"
    assignee_id = alloc.team_id if alloc.team_id else (alloc.assignee_user_soeid or "")
    assignee_name = alloc.assignee
    if assignee_type == "team" and not assignee_name:
        assignee_name = team_display_name(session, alloc.team_id, space_ctx)
    return WorkAllocationAssignmentRead(
        id=alloc.allocation_id,
        task_id=alloc.work_item_id,
        assignee_type=assignee_type,
        assignee_id=assignee_id,
        assignee_name=assignee_name,
        month=month_token(month_value),
        fte_months_allocated=round(max(fte, 0.0), 3),
    )


def _resolve_work_allocation_assignee(
    session: Session,
    assignee_type: Literal["person", "team"],
    assignee_id: str,
    space_ctx: SpaceContext,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    assignee_user_soeid: Optional[str] = None
    assignee_name: Optional[str] = None
    team_id: Optional[str] = None
    if assignee_type == "person":
        user = active_person_by_soeid(session, assignee_id, space_ctx)
        assignee_user_soeid = user.soeid
        assignee_name = user.display_name
    else:
        team = _active_team(session, assignee_id, space_ctx)
        team_id = team.team_id
        assignee_name = team.name
    return assignee_user_soeid, assignee_name, team_id


def _ensure_work_allocation_assignment_available(
    session: Session,
    space_ctx: SpaceContext,
    task_id: str,
    month_start: date,
    assignee_user_soeid: Optional[str],
    team_id: Optional[str],
    *,
    exclude_allocation_id: Optional[str] = None,
) -> None:
    same_assignee = (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == task_id)
        .filter(_allocation_month_expr() == month_start)
    )
    if exclude_allocation_id:
        same_assignee = same_assignee.filter(ResourceAllocation.allocation_id != exclude_allocation_id)
    if assignee_user_soeid:
        same_assignee = same_assignee.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
    else:
        same_assignee = (
            same_assignee
            .filter(ResourceAllocation.assignee_user_soeid.is_(None))
            .filter(ResourceAllocation.team_id == team_id)
        )
    if same_assignee.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already allocated to this assignee for this month",
        )

    if team_id:
        other_team_allocation = (
            _allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id == task_id)
            .filter(_allocation_month_expr() == month_start)
            .filter(ResourceAllocation.assignee_user_soeid.is_(None))
        )
        if exclude_allocation_id:
            other_team_allocation = other_team_allocation.filter(ResourceAllocation.allocation_id != exclude_allocation_id)
        other_team_allocation = other_team_allocation.first()
        if other_team_allocation and other_team_allocation.team_id != team_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Task already has a team-level allocation for this month",
            )


def _work_allocation_revival_query(
    session: Session,
    space_ctx: SpaceContext,
    task_id: str,
    month_start: date,
    assignee_user_soeid: Optional[str],
    *,
    exclude_allocation_id: Optional[str] = None,
):
    revive_query = (
        session.query(ResourceAllocation)
        .filter(ResourceAllocation.space_id == space_ctx.space_id)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == task_id)
        .filter(ResourceAllocation.week_start == month_start)
        .filter(ResourceAllocation.window_id.is_(None))
    )
    if exclude_allocation_id:
        revive_query = revive_query.filter(ResourceAllocation.allocation_id != exclude_allocation_id)
    if assignee_user_soeid:
        revive_query = revive_query.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
    else:
        revive_query = revive_query.filter(ResourceAllocation.assignee_user_soeid.is_(None))
    return revive_query


def _raise_on_unique_allocation_conflict(err: IntegrityError) -> None:
    message = str(getattr(err, "orig", err) or "").upper()
    if _WORK_ALLOCATION_UNIQUE_CONSTRAINT in message:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already allocated to this assignee for this month",
        ) from err
    raise err


def _raise_window_name_conflict(err: IntegrityError) -> None:
    if _is_window_name_conflict_integrity_error(err):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning window name already exists",
        ) from err


def _is_window_name_conflict_integrity_error(err: IntegrityError) -> bool:
    text = " ".join(
        [
            str(err),
            str(getattr(err, "orig", "")),
            str(getattr(err, "statement", "")),
        ]
    ).lower()
    if "uix_planning_window_name" in text:
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
    return "tb_ta_pm_planning_windows" in text or "planning_window" in text


def _is_team_name_conflict_integrity_error(err: IntegrityError) -> bool:
    text = " ".join(
        [
            str(err),
            str(getattr(err, "orig", "")),
            str(getattr(err, "statement", "")),
        ]
    ).lower()
    if "uix_team_space_name" in text or "uix_team_name" in text:
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
    return "tb_ta_pm_teams" in text or "team" in text


def _raise_team_name_conflict(err: IntegrityError) -> None:
    if _is_team_name_conflict_integrity_error(err):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team already exists",
        ) from err


def _raise_team_rename_conflict(err: IntegrityError) -> None:
    if _is_team_name_conflict_integrity_error(err):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name already exists",
        ) from err


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
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
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
        assignee_user_soeid=payload.assignee_user_soeid,
        assignee=payload.assignee,
        team_id=payload.team_id,
        week_start=payload.week_start or month_start,
        month_start=month_start,
        hours=_hours_from_fte_months(fte_months),
        fte_months=fte_months,
        window_id=payload.window_id,
    )
    session.add(alloc)
    _commit_planning_mutation(session, space_ctx, refresh=alloc)
    return ResourceAllocationRead.model_validate(_allocation_to_payload(alloc))


@router.patch("/resource-allocations/{allocation_id}", response_model=ResourceAllocationRead)
def update_allocation(
    allocation_id: str,
    payload: ResourceAllocationUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
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
    _commit_planning_mutation(session, space_ctx, refresh=alloc)
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
    _commit_planning_mutation(session, space_ctx)
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
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> PlanningWindowRead:
    win = PlanningWindow(
        space_id=space_ctx.space_id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    session.add(win)
    _commit_planning_mutation(
        session,
        space_ctx,
        refresh=win,
        on_integrity_error=_raise_window_name_conflict,
    )
    return PlanningWindowRead.model_validate(win)


@router.patch("/planning/windows/{window_id}", response_model=PlanningWindowRead)
def update_window(
    window_id: str,
    payload: PlanningWindowUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> PlanningWindowRead:
    win = _get_window(session, window_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(win, field, val)
    win.updated_at = datetime.now(timezone.utc)
    session.add(win)
    _commit_planning_mutation(
        session,
        space_ctx,
        refresh=win,
        on_integrity_error=_raise_window_name_conflict,
    )
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
    _commit_planning_mutation(session, space_ctx)
    return None


# Work Allocation Board (MVP)
@router.get("/planning/work-allocation/teams", response_model=List[WorkAllocationTeamRead])
def list_work_allocation_teams(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationTeamRead]:
    rows = _team_query(session, space_ctx).order_by(Team.name.asc()).all()
    return [WorkAllocationTeamRead(id=row.team_id, name=row.name) for row in rows]


@router.post(
    "/planning/work-allocation/teams",
    response_model=WorkAllocationTeamRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_team(
    payload: WorkAllocationTeamCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTeamRead:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team name is required")

    existing = (
        session.query(Team)
        .filter(Team.space_id == space_ctx.space_id)
        .filter(func.lower(Team.name) == name.lower())
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing and existing.deleted_at is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team already exists")
    if existing and existing.deleted_at is not None:
        existing.deleted_at = None
        existing.updated_at = now
        existing.name = name
        session.add(existing)
        _commit_planning_mutation(
            session,
            space_ctx,
            cache_keys=("teams", "planning"),
        )
        return WorkAllocationTeamRead(id=existing.team_id, name=existing.name)

    row = Team(
        space_id=space_ctx.space_id,
        name=name,
        capacity_unit="fte_month",
        default_capacity_per_week=0,
        default_capacity_fte_month=0.0,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("teams", "planning"),
        refresh=row,
        on_integrity_error=_raise_team_name_conflict,
    )
    return WorkAllocationTeamRead(id=row.team_id, name=row.name)


@router.patch("/planning/work-allocation/teams/{team_id}", response_model=WorkAllocationTeamRead)
def update_work_allocation_team(
    team_id: str,
    payload: WorkAllocationTeamUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTeamRead:
    row = _active_team(session, team_id, space_ctx)
    next_name = (payload.name or "").strip() if payload.name is not None else None
    if next_name:
        conflict = (
            session.query(Team)
            .filter(Team.space_id == space_ctx.space_id)
            .filter(Team.deleted_at.is_(None))
            .filter(func.lower(Team.name) == next_name.lower())
            .filter(Team.team_id != team_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team name already exists")
        old_name = row.name
        row.name = next_name
        for user in active_space_user_query(session, space_ctx).filter(User.team_tag == old_name).all():
            user.team_tag = next_name
            session.add(user)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("teams", "users", "planning"),
        refresh=row,
        on_integrity_error=_raise_team_rename_conflict,
    )
    return WorkAllocationTeamRead(id=row.team_id, name=row.name)


@router.delete("/planning/work-allocation/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_team(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    row = _active_team(session, team_id, space_ctx)
    now = datetime.now(timezone.utc)
    old_name = row.name
    row.deleted_at = now
    session.add(row)
    for user in active_space_user_query(session, space_ctx).filter(User.team_tag == old_name).all():
        user.team_tag = None
        user.updated_at = now
        session.add(user)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("teams", "users", "planning"),
    )
    return None


@router.get("/planning/work-allocation/people", response_model=List[WorkAllocationPersonRead])
def list_work_allocation_people(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationPersonRead]:
    team_map = team_name_to_id_map(session, space_ctx)
    rows = active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()
    return [_person_payload(row, team_map) for row in rows]


@router.post(
    "/planning/work-allocation/people",
    response_model=WorkAllocationPersonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_person(
    payload: WorkAllocationPersonCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationPersonRead:
    name = (payload.name or "").strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Person name is required")
    team = _active_team(session, payload.team_id, space_ctx) if payload.team_id else None
    soeid = next_available_soeid(session, name)
    now = datetime.now(timezone.utc)
    raw_capacity = payload.capacity_fte_months if payload.capacity_fte_months is not None else 1.0
    cap = max(float(raw_capacity), 0.0)
    row = User(
        soeid=soeid,
        email=f"{soeid}@{WORK_ALLOCATION_DOMAIN}",
        display_name=name,
        password_hash=hash_bootstrap_password(),
        role="user",
        is_active=True,
        team_tag=team.name if team else None,
        capacity_fte_month=round(cap, 3),
        capacity_hours=max(int(round(cap * 40.0)), 0),
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    ensure_membership(session, row.user_id, space_ctx.space_id)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("users", "planning"),
        refresh=row,
    )
    team_map = team_name_to_id_map(session, space_ctx)
    return _person_payload(row, team_map)


@router.patch("/planning/work-allocation/people/{person_id}", response_model=WorkAllocationPersonRead)
def update_work_allocation_person(
    person_id: str,
    payload: WorkAllocationPersonUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationPersonRead:
    row = active_person_by_soeid(session, person_id, space_ctx)
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        row.display_name = (str(updates.get("name") or "").strip() or row.display_name)

    if "team_id" in updates:
        next_team_id = updates.get("team_id")
        team = _active_team(session, next_team_id, space_ctx) if next_team_id else None
        row.team_tag = team.name if team else None

    if "capacity_fte_months" in updates and updates.get("capacity_fte_months") is not None:
        cap = max(float(updates["capacity_fte_months"]), 0.0)
        row.capacity_fte_month = round(cap, 3)
        row.capacity_hours = max(int(round(cap * 40.0)), 0)

    if "active" in updates and updates.get("active") is not None:
        row.is_active = bool(updates["active"])

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("users", "planning"),
        refresh=row,
    )
    team_map = team_name_to_id_map(session, space_ctx)
    return _person_payload(row, team_map)


@router.delete("/planning/work-allocation/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_person(
    person_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    row = active_person_by_soeid(session, person_id, space_ctx)
    now = datetime.now(timezone.utc)
    row.is_active = False
    row.updated_at = now
    session.add(row)
    membership = (
        session.query(SpaceMembership)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.user_id == row.user_id)
        .first()
    )
    if membership:
        membership.status = "inactive"
        membership.updated_at = now
        session.add(membership)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("users", "planning"),
    )
    return None


@router.get("/planning/work-allocation/tasks", response_model=List[WorkAllocationTaskRead])
def list_work_allocation_tasks(
    month: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationTaskRead]:
    month_start = month_from_token(month or month_token(None))
    query = planning_task_query(session, space_ctx)
    if search:
        term = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(Subcomponent.subcomponent_name).like(term))
    tasks = query.order_by(Subcomponent.created_at.asc()).all()
    task_ids = [t.subcomponent_id for t in tasks]
    assigned_ids: set[str] = set()
    if task_ids:
        for row in (
            _allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(_allocation_month_expr() == month_start)
            .all()
        ):
            assigned_ids.add(row.work_item_id)
    return [_task_payload(task, assigned_ids) for task in tasks]


@router.post(
    "/planning/work-allocation/tasks",
    response_model=WorkAllocationTaskRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_task(
    payload: WorkAllocationTaskCreate,
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTaskRead:
    solution = board_solution(session, space_ctx)
    query = planning_task_query(session, space_ctx).filter(Subcomponent.solution_id == solution.solution_id)
    title = (payload.title or "").strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title is required")
    conflict = query.filter(func.lower(Subcomponent.subcomponent_name) == title.lower()).first()
    if conflict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists")
    raw_fte = payload.fte_months if payload.fte_months is not None else 0.25
    fte = round(max(float(raw_fte), 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
    now = datetime.now(timezone.utc)
    row = Subcomponent(
        space_id=space_ctx.space_id,
        project_id=solution.project_id,
        solution_id=solution.solution_id,
        subcomponent_name=title,
        status=SubcomponentStatus.to_do,
        priority=3,
        assignee=WORK_ALLOCATION_DEFAULT_ASSIGNEE,
        estimate_hours=hours,
        capacity_hours=hours,
        blocked=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("subcomponents", "planning"),
        refresh=row,
    )
    month_start = month_from_token(month or month_token(None))
    assigned_ids: set[str] = set()
    if (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == row.subcomponent_id)
        .filter(_allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.subcomponent_id)
    return _task_payload(row, assigned_ids)


@router.patch("/planning/work-allocation/tasks/{task_id}", response_model=WorkAllocationTaskRead)
def update_work_allocation_task(
    task_id: str,
    month: Optional[str] = Query(None),
    payload: WorkAllocationTaskUpdate = ...,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationTaskRead:
    query = planning_task_query(session, space_ctx)
    row = query.filter(Subcomponent.subcomponent_id == task_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title is required")
        conflict = (
            query.filter(Subcomponent.solution_id == row.solution_id)
            .filter(func.lower(Subcomponent.subcomponent_name) == title.lower())
            .filter(Subcomponent.subcomponent_id != task_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists")
        row.subcomponent_name = title
    if payload.fte_months is not None:
        fte = round(max(float(payload.fte_months), 0.05), 3)
        hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
        row.estimate_hours = hours
        row.capacity_hours = hours
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("subcomponents", "planning"),
        refresh=row,
    )
    month_start = month_from_token(month or month_token(None))
    assigned_ids: set[str] = set()
    if (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == row.subcomponent_id)
        .filter(_allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.subcomponent_id)
    return _task_payload(row, assigned_ids)


@router.delete("/planning/work-allocation/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_task(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    query = planning_task_query(session, space_ctx)
    row = query.filter(Subcomponent.subcomponent_id == task_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    for alloc in (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == task_id)
        .all()
    ):
        alloc.deleted_at = now
        alloc.updated_at = now
        session.add(alloc)
    _commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("subcomponents", "planning"),
    )
    return None


@router.get("/planning/work-allocation/allocations", response_model=List[WorkAllocationAssignmentRead])
def list_work_allocation_allocations(
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationAssignmentRead]:
    month_start = month_from_token(month or month_token(None))
    query = planning_task_query(session, space_ctx)
    task_ids = [row.subcomponent_id for row in query.all()]
    if not task_ids:
        return []
    rows = (
        _allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id.in_(task_ids))
        .filter(_allocation_month_expr() == month_start)
        .order_by(ResourceAllocation.created_at.asc())
        .all()
    )
    return [_allocation_for_board_payload(row, space_ctx, session) for row in rows]


@router.get("/planning/work-allocation/report.pdf")
def download_work_allocation_report_pdf(
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> StreamingResponse:
    month_start = month_from_token(month or month_token(None))
    month_token_value = month_token(month_start)

    team_rows = _team_query(session, space_ctx).order_by(Team.name.asc()).all()
    team_map = team_name_to_id_map(session, space_ctx)
    people_rows = active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()
    people_payload = [_person_payload(row, team_map).model_dump() for row in people_rows]

    task_query = planning_task_query(session, space_ctx)
    task_rows = task_query.order_by(Subcomponent.subcomponent_name.asc()).all()
    task_payload = [
        {
            "id": row.subcomponent_id,
            "title": row.subcomponent_name,
            "fte_months": task_fte_months(row, hours_per_fte_month=_HOURS_PER_FTE_MONTH),
        }
        for row in task_rows
    ]
    task_ids = [row.subcomponent_id for row in task_rows]
    allocation_rows: list[ResourceAllocation] = []
    if task_ids:
        allocation_rows = (
            _allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(_allocation_month_expr() == month_start)
            .order_by(ResourceAllocation.created_at.asc())
            .all()
        )

    allocation_payload = [
        _allocation_for_board_payload(row, space_ctx, session).model_dump()
        for row in allocation_rows
    ]
    pdf_bytes = build_work_allocation_report_pdf(
        month_token=month_token_value,
        space_name=space_ctx.space_name,
        teams=[{"id": row.team_id, "name": row.name} for row in team_rows],
        people=people_payload,
        tasks=task_payload,
        allocations=allocation_payload,
    )
    filename = f"work-allocation-report-{month_token_value}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.post(
    "/planning/work-allocation/allocations",
    response_model=WorkAllocationAssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_allocation(
    payload: WorkAllocationAssignmentCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationAssignmentRead:
    month_start = month_from_token(payload.month)
    task_query = planning_task_query(session, space_ctx)
    task = task_query.filter(Subcomponent.subcomponent_id == payload.task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    assignee_user_soeid, assignee_name, team_id = _resolve_work_allocation_assignee(
        session, payload.assignee_type, payload.assignee_id, space_ctx
    )
    _ensure_work_allocation_assignment_available(
        session,
        space_ctx,
        payload.task_id,
        month_start,
        assignee_user_soeid,
        team_id,
    )

    fte = payload.fte_months_allocated
    if fte is None:
        fte = task_fte_months(task, hours_per_fte_month=_HOURS_PER_FTE_MONTH)
    fte = round(max(float(fte), 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
    now = datetime.now(timezone.utc)

    # Oracle unique key on allocations includes assignee_user_soeid/week_start/window_id but not deleted_at.
    # Reuse a matching soft-deleted row to avoid ORA-00001 on re-assignment flows.
    revive_query = _work_allocation_revival_query(
        session,
        space_ctx,
        payload.task_id,
        month_start,
        assignee_user_soeid,
    )
    revive_row = revive_query.first()
    if revive_row:
        revive_row.assignee_user_soeid = assignee_user_soeid
        revive_row.assignee = assignee_name
        revive_row.team_id = team_id
        revive_row.week_start = month_start
        revive_row.month_start = month_start
        revive_row.hours = hours
        revive_row.fte_months = fte
        revive_row.window_id = None
        revive_row.deleted_at = None
        revive_row.updated_at = now
        session.add(revive_row)
        _commit_planning_mutation(
            session,
            space_ctx,
            refresh=revive_row,
            on_integrity_error=_raise_on_unique_allocation_conflict,
        )
        return _allocation_for_board_payload(revive_row, space_ctx, session)

    row = ResourceAllocation(
        space_id=space_ctx.space_id,
        work_item_type="subcomponent",
        work_item_id=payload.task_id,
        assignee_user_soeid=assignee_user_soeid,
        assignee=assignee_name,
        team_id=team_id,
        week_start=month_start,
        month_start=month_start,
        hours=hours,
        fte_months=fte,
        window_id=None,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        refresh=row,
        on_integrity_error=_raise_on_unique_allocation_conflict,
    )
    return _allocation_for_board_payload(row, space_ctx, session)


@router.patch(
    "/planning/work-allocation/allocations/{allocation_id}",
    response_model=WorkAllocationAssignmentRead,
)
def update_work_allocation_allocation(
    allocation_id: str,
    payload: WorkAllocationAssignmentUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> WorkAllocationAssignmentRead:
    row = _get_allocation(session, allocation_id, space_ctx)
    if row.work_item_type != "subcomponent":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Allocation is not a planning task assignment")

    month_start = row.month_start or (_month_start(row.week_start) if row.week_start else None)
    if month_start is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Allocation month is missing")

    task = (
        planning_task_query(session, space_ctx)
        .filter(Subcomponent.subcomponent_id == row.work_item_id)
        .first()
    )
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    assignee_user_soeid, assignee_name, team_id = _resolve_work_allocation_assignee(
        session, payload.assignee_type, payload.assignee_id, space_ctx
    )
    _ensure_work_allocation_assignment_available(
        session,
        space_ctx,
        row.work_item_id,
        month_start,
        assignee_user_soeid,
        team_id,
        exclude_allocation_id=row.allocation_id,
    )

    fte = payload.fte_months_allocated
    if fte is None:
        fte = float(row.fte_months or 0.0)
        if fte <= 0:
            fte = task_fte_months(task, hours_per_fte_month=_HOURS_PER_FTE_MONTH)
    fte = round(max(float(fte), 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
    now = datetime.now(timezone.utc)

    revive_row = _work_allocation_revival_query(
        session,
        space_ctx,
        row.work_item_id,
        month_start,
        assignee_user_soeid,
        exclude_allocation_id=row.allocation_id,
    ).first()
    if revive_row and revive_row.deleted_at is not None:
        revive_row.assignee_user_soeid = assignee_user_soeid
        revive_row.assignee = assignee_name
        revive_row.team_id = team_id
        revive_row.week_start = month_start
        revive_row.month_start = month_start
        revive_row.hours = hours
        revive_row.fte_months = fte
        revive_row.window_id = None
        revive_row.deleted_at = None
        revive_row.updated_at = now
        row.deleted_at = now
        row.updated_at = now
        session.add(revive_row)
        session.add(row)
        _commit_planning_mutation(
            session,
            space_ctx,
            refresh=revive_row,
            on_integrity_error=_raise_on_unique_allocation_conflict,
        )
        return _allocation_for_board_payload(revive_row, space_ctx, session)

    row.assignee_user_soeid = assignee_user_soeid
    row.assignee = assignee_name
    row.team_id = team_id
    row.week_start = month_start
    row.month_start = month_start
    row.hours = hours
    row.fte_months = fte
    row.window_id = None
    row.updated_at = now
    session.add(row)
    _commit_planning_mutation(
        session,
        space_ctx,
        refresh=row,
        on_integrity_error=_raise_on_unique_allocation_conflict,
    )
    return _allocation_for_board_payload(row, space_ctx, session)


@router.delete("/planning/work-allocation/allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    row = _get_allocation(session, allocation_id, space_ctx)
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    _commit_planning_mutation(session, space_ctx)
    return None
