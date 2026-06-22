from datetime import date
from typing import Literal, Optional

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import PlanningWindow, ResourceAllocation, Task, Team, User
from ...services.planning_work_allocation import (
    active_person_by_soeid,
    month_token,
    task_fte_months,
    team_display_name,
)
from ...services.spaces import SpaceContext
from ...services.mutations import commit_refresh_and_publish, commit_session, publish_space_mutation
from ...schemas.planning import (
    WorkAllocationAssignmentRead,
    WorkAllocationPersonRead,
    WorkAllocationTaskRead,
)


_PLANNING_LIST_TTL_SECONDS = 20
_PLANNING_DETAIL_TTL_SECONDS = 30
_HOURS_PER_FTE_MONTH = 160.0
_WORK_ALLOCATION_UNIQUE_CONSTRAINT = "UIX_ALLOC_UNIQUE_ASSIGNMENT"


def role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def commit_planning_mutation(
    session: Session,
    space_ctx: SpaceContext,
    *,
    cache_keys: tuple[str, ...] = ("planning",),
    refresh: object | None = None,
    broadcast_channel: str | None = "all",
    on_integrity_error=None,
) -> None:
    if refresh is None:
        commit_session(session, on_integrity_error=on_integrity_error)
        publish_space_mutation(
            space_ctx.space_id,
            cache_keys,
            broadcast_channel=broadcast_channel,
        )
        return
    commit_refresh_and_publish(
        session,
        refresh,
        space_id=space_ctx.space_id,
        cache_keys=cache_keys,
        broadcast_channel=broadcast_channel,
        on_integrity_error=on_integrity_error,
    )


def allocation_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(ResourceAllocation)
        .filter(ResourceAllocation.deleted_at.is_(None))
        .filter(ResourceAllocation.space_id == space_ctx.space_id)
    )


def window_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(PlanningWindow)
        .filter(PlanningWindow.deleted_at.is_(None))
        .filter(PlanningWindow.space_id == space_ctx.space_id)
    )


def team_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
    )


def active_team(session: Session, team_id: Optional[str], space_ctx: SpaceContext) -> Optional[Team]:
    if not team_id:
        return None
    row = team_query(session, space_ctx).filter(Team.team_id == team_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return row


def get_allocation(session: Session, alloc_id: str, space_ctx: SpaceContext) -> ResourceAllocation:
    alloc = allocation_query(session, space_ctx).filter(ResourceAllocation.allocation_id == alloc_id).first()
    if not alloc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Allocation not found")
    return alloc


def get_window(session: Session, window_id: str, space_ctx: SpaceContext) -> PlanningWindow:
    win = window_query(session, space_ctx).filter(PlanningWindow.window_id == window_id).first()
    if not win:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planning window not found")
    return win


def month_start(value: date) -> date:
    return value.replace(day=1)


def resolve_month_start(month_start_value: Optional[date], week_start: Optional[date]) -> date:
    raw = month_start_value or week_start
    if raw is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="month_start (or legacy week_start) is required",
        )
    return month_start(raw)


def resolve_fte_months(fte_months: Optional[float], hours: Optional[int]) -> float:
    if fte_months is not None:
        return round(max(float(fte_months), 0.0), 3)
    if hours is not None:
        return round(max(float(hours), 0.0) / _HOURS_PER_FTE_MONTH, 3)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="fte_months (or legacy hours) is required",
    )


def hours_from_fte_months(value: float) -> int:
    return max(int(round(float(value) * _HOURS_PER_FTE_MONTH)), 0)


def allocation_month_expr():
    return func.coalesce(ResourceAllocation.month_start, ResourceAllocation.week_start)


def allocation_fte_expr():
    return func.coalesce(ResourceAllocation.fte_months, (ResourceAllocation.hours / _HOURS_PER_FTE_MONTH))


def allocation_to_payload(alloc: ResourceAllocation) -> dict:
    normalized_month_start = alloc.month_start or (month_start(alloc.week_start) if alloc.week_start else None)
    week_start = alloc.week_start or normalized_month_start
    fte_months = float(alloc.fte_months or 0.0)
    if fte_months <= 0 and alloc.hours:
        fte_months = round(float(alloc.hours) / _HOURS_PER_FTE_MONTH, 3)
    hours = alloc.hours if alloc.hours is not None else hours_from_fte_months(fte_months)
    return {
        "allocation_id": alloc.allocation_id,
        "work_item_type": alloc.work_item_type,
        "work_item_id": alloc.work_item_id,
        "assignee": alloc.assignee,
        "assignee_user_soeid": alloc.assignee_user_soeid,
        "team_id": alloc.team_id,
        "month_start": normalized_month_start.isoformat() if normalized_month_start else None,
        "fte_months": round(fte_months, 3),
        "week_start": week_start.isoformat() if week_start else None,
        "hours": int(hours or 0),
        "window_id": alloc.window_id,
        "created_at": alloc.created_at,
        "updated_at": alloc.updated_at,
    }


def person_payload(user: User, team_map: dict[str, str]) -> WorkAllocationPersonRead:
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


def task_payload(task: Task, assigned_ids: set[str]) -> WorkAllocationTaskRead:
    return WorkAllocationTaskRead(
        id=task.task_id,
        title=task.task_name,
        fte_months=task_fte_months(
            task,
            hours_per_fte_month=_HOURS_PER_FTE_MONTH,
        ),
        status="assigned" if task.task_id in assigned_ids else "backlog",
    )


def allocation_for_board_payload(
    alloc: ResourceAllocation,
    space_ctx: SpaceContext,
    session: Session,
) -> WorkAllocationAssignmentRead:
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


def resolve_work_allocation_assignee(
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
        team = active_team(session, assignee_id, space_ctx)
        team_id = team.team_id
        assignee_name = team.name
    return assignee_user_soeid, assignee_name, team_id


def ensure_work_allocation_assignment_available(
    session: Session,
    space_ctx: SpaceContext,
    task_id: str,
    month_start_value: date,
    assignee_user_soeid: Optional[str],
    team_id: Optional[str],
    *,
    exclude_allocation_id: Optional[str] = None,
) -> None:
    same_assignee = (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "task")
        .filter(ResourceAllocation.work_item_id == task_id)
        .filter(allocation_month_expr() == month_start_value)
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

    if not team_id:
        return

    other_team_allocation = (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "task")
        .filter(ResourceAllocation.work_item_id == task_id)
        .filter(allocation_month_expr() == month_start_value)
        .filter(ResourceAllocation.assignee_user_soeid.is_(None))
    )
    if exclude_allocation_id:
        other_team_allocation = other_team_allocation.filter(ResourceAllocation.allocation_id != exclude_allocation_id)
    existing = other_team_allocation.first()
    if existing and existing.team_id != team_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task already has a team-level allocation for this month",
        )


def work_allocation_revival_query(
    session: Session,
    space_ctx: SpaceContext,
    task_id: str,
    month_start_value: date,
    assignee_user_soeid: Optional[str],
    *,
    exclude_allocation_id: Optional[str] = None,
):
    revive_query = (
        session.query(ResourceAllocation)
        .filter(ResourceAllocation.space_id == space_ctx.space_id)
        .filter(ResourceAllocation.work_item_type == "task")
        .filter(ResourceAllocation.work_item_id == task_id)
        .filter(ResourceAllocation.week_start == month_start_value)
        .filter(ResourceAllocation.window_id.is_(None))
    )
    if exclude_allocation_id:
        revive_query = revive_query.filter(ResourceAllocation.allocation_id != exclude_allocation_id)
    if assignee_user_soeid:
        revive_query = revive_query.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
    else:
        revive_query = revive_query.filter(ResourceAllocation.assignee_user_soeid.is_(None))
    return revive_query


def raise_on_unique_allocation_conflict(err: IntegrityError) -> None:
    message = str(getattr(err, "orig", err) or "").upper()
    if _WORK_ALLOCATION_UNIQUE_CONSTRAINT in message:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Task is already allocated to this assignee for this month",
        ) from err
    raise err


def raise_window_name_conflict(err: IntegrityError) -> None:
    if is_window_name_conflict_integrity_error(err):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Planning window name already exists",
        ) from err


def is_window_name_conflict_integrity_error(err: IntegrityError) -> bool:
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


def is_team_name_conflict_integrity_error(err: IntegrityError) -> bool:
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


def raise_team_name_conflict(err: IntegrityError) -> None:
    if is_team_name_conflict_integrity_error(err):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team already exists",
        ) from err


def raise_team_rename_conflict(err: IntegrityError) -> None:
    if is_team_name_conflict_integrity_error(err):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name already exists",
        ) from err
