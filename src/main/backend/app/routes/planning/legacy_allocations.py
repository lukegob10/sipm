import csv
from datetime import date, datetime, timezone
from io import StringIO
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ...models import PlanningWindow, Project, ResourceAllocation, Solution, Task, Team, User
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
from ...utils import normalize_str, parse_date, read_csv
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
_WINDOW_EXPORT_FIELDNAMES = ["window_name", "start_date", "end_date"]
_ALLOCATION_EXPORT_FIELDNAMES = [
    "work_item_type",
    "work_item_id",
    "project_name",
    "solution_name",
    "version",
    "task_name",
    "assignee",
    "assignee_user_soeid",
    "team_name",
    "month_start",
    "fte_months",
    "hours",
    "window_name",
]


def _bool_query(value: bool) -> bool:
    return bool(value)


def _write_csv(fieldnames: list[str], rows: list[dict]) -> StringIO:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buffer.seek(0)
    return buffer


def _project_by_name(session: Session, space_ctx: SpaceContext, name: str) -> Project | None:
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(func.lower(Project.project_name) == name.lower())
        .first()
    )


def _solution_by_natural_key(
    session: Session,
    space_ctx: SpaceContext,
    *,
    project_name: str,
    solution_name: str,
    version: str,
) -> Solution | None:
    project = _project_by_name(session, space_ctx, project_name)
    if not project:
        return None
    return (
        session.query(Solution)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Solution.project_id == project.project_id)
        .filter(func.lower(Solution.solution_name) == solution_name.lower())
        .filter(func.lower(Solution.version) == version.lower())
        .first()
    )


def _task_by_natural_key(
    session: Session,
    space_ctx: SpaceContext,
    *,
    project_name: str,
    solution_name: str,
    version: str,
    task_name: str,
) -> Task | None:
    solution = _solution_by_natural_key(
        session,
        space_ctx,
        project_name=project_name,
        solution_name=solution_name,
        version=version,
    )
    if not solution:
        return None
    return (
        session.query(Task)
        .filter(Task.deleted_at.is_(None))
        .filter(Task.space_id == space_ctx.space_id)
        .filter(Task.solution_id == solution.solution_id)
        .filter(func.lower(Task.task_name) == task_name.lower())
        .first()
    )


def _resolve_allocation_work_item(session: Session, space_ctx: SpaceContext, row: dict, row_num: int) -> str:
    work_item_id = normalize_str(row.get("work_item_id"))
    work_item_type = normalize_str(row.get("work_item_type")).lower()
    project_name = normalize_str(row.get("project_name"))
    solution_name = normalize_str(row.get("solution_name"))
    version = normalize_str(row.get("version")) or "0.1.0"
    task_name = normalize_str(row.get("task_name"))
    if work_item_type == "project" and project_name:
        project = _project_by_name(session, space_ctx, project_name)
        if not project:
            raise ValueError(f"Row {row_num}: project_name '{project_name}' does not exist")
        return project.project_id
    if work_item_type == "solution" and project_name and solution_name:
        solution = _solution_by_natural_key(
            session,
            space_ctx,
            project_name=project_name,
            solution_name=solution_name,
            version=version,
        )
        if not solution:
            raise ValueError(
                f"Row {row_num}: solution '{solution_name}' version '{version}' for project '{project_name}' does not exist"
            )
        return solution.solution_id
    if work_item_type == "task" and project_name and solution_name and task_name:
        task = _task_by_natural_key(
            session,
            space_ctx,
            project_name=project_name,
            solution_name=solution_name,
            version=version,
            task_name=task_name,
        )
        if not task:
            raise ValueError(
                f"Row {row_num}: task '{task_name}' for solution '{solution_name}' does not exist"
            )
        return task.task_id
    if work_item_id:
        return work_item_id
    raise ValueError(f"Row {row_num}: work item natural key or work_item_id is required")


def _team_by_name(session: Session, space_ctx: SpaceContext, name: str) -> Team | None:
    return (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
        .filter(func.lower(Team.name) == name.lower())
        .first()
    )


def _window_by_name(session: Session, space_ctx: SpaceContext, name: str) -> PlanningWindow | None:
    return window_query(session, space_ctx).filter(func.lower(PlanningWindow.name) == name.lower()).first()


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


@router.get("/resource-allocations/export")
def export_resource_allocations(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    allocations = allocation_query(session, space_ctx).order_by(allocation_month_expr().asc(), ResourceAllocation.created_at.asc()).all()
    project_map = {
        row.project_id: row
        for row in session.query(Project).filter(Project.deleted_at.is_(None)).filter(Project.space_id == space_ctx.space_id).all()
    }
    solution_map = {
        row.solution_id: row
        for row in session.query(Solution).filter(Solution.deleted_at.is_(None)).filter(Solution.space_id == space_ctx.space_id).all()
    }
    task_map = {
        row.task_id: row
        for row in session.query(Task)
        .filter(Task.deleted_at.is_(None))
        .filter(Task.space_id == space_ctx.space_id)
        .all()
    }
    team_map = {
        row.team_id: row.name
        for row in session.query(Team).filter(Team.deleted_at.is_(None)).filter(Team.space_id == space_ctx.space_id).all()
    }
    window_map = {
        row.window_id: row.name
        for row in window_query(session, space_ctx).all()
    }
    rows = []
    for alloc in allocations:
        project_name = solution_name = version = task_name = ""
        if alloc.work_item_type == "project":
            project = project_map.get(alloc.work_item_id)
            project_name = project.project_name if project else ""
        elif alloc.work_item_type == "solution":
            solution = solution_map.get(alloc.work_item_id)
            if solution:
                project = project_map.get(solution.project_id)
                project_name = project.project_name if project else ""
                solution_name = solution.solution_name
                version = solution.version
        elif alloc.work_item_type == "task":
            task = task_map.get(alloc.work_item_id)
            if task:
                project = project_map.get(task.project_id)
                solution = solution_map.get(task.solution_id)
                project_name = project.project_name if project else ""
                solution_name = solution.solution_name if solution else ""
                version = solution.version if solution else ""
                task_name = task.task_name
        payload = allocation_to_payload(alloc)
        rows.append(
            {
                "work_item_type": alloc.work_item_type,
                "work_item_id": alloc.work_item_id,
                "project_name": project_name,
                "solution_name": solution_name,
                "version": version,
                "task_name": task_name,
                "assignee": alloc.assignee or "",
                "assignee_user_soeid": alloc.assignee_user_soeid or "",
                "team_name": team_map.get(alloc.team_id, ""),
                "month_start": payload["month_start"] or "",
                "fte_months": payload["fte_months"],
                "hours": payload["hours"],
                "window_name": window_map.get(alloc.window_id, ""),
            }
        )
    headers = {"Content-Disposition": 'attachment; filename="resource-allocations.csv"'}
    return StreamingResponse(_write_csv(_ALLOCATION_EXPORT_FIELDNAMES, rows), media_type="text/csv", headers=headers)


@router.post("/resource-allocations/import")
def import_resource_allocations(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    dry_run: bool = False,
    atomic: bool = False,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"created": 0, "updated": 0, "errors": errors, "total_rows": 0, "dry_run": _bool_query(dry_run)}
    records = []
    seen = set()
    created = updated = 0
    for idx, row in enumerate(rows, start=2):
        try:
            work_item_type = normalize_str(row.get("work_item_type")).lower()
            if work_item_type not in {"project", "solution", "task"}:
                raise ValueError(f"Row {idx}: work_item_type must be project, solution, or task")
            work_item_id = _resolve_allocation_work_item(session, space_ctx, row, idx)
            month_value = parse_date(row.get("month_start"))
            if month_value is None:
                raise ValueError(f"Row {idx}: month_start is required")
            normalized_month = month_start(month_value)
            fte_raw = normalize_str(row.get("fte_months"))
            hours_raw = normalize_str(row.get("hours"))
            if fte_raw:
                fte_months = round(max(float(fte_raw), 0.0), 3)
                hours = hours_from_fte_months(fte_months)
            elif hours_raw:
                hours = max(int(hours_raw), 0)
                fte_months = round(float(hours) / _HOURS_PER_FTE_MONTH, 3)
            else:
                raise ValueError(f"Row {idx}: fte_months or hours is required")
            team_name = normalize_str(row.get("team_name"))
            team_id = normalize_str(row.get("team_id")) or None
            if team_name:
                team = _team_by_name(session, space_ctx, team_name)
                if not team:
                    raise ValueError(f"Row {idx}: team_name '{team_name}' does not exist")
                team_id = team.team_id
            elif team_id:
                active_team(session, team_id, space_ctx)
            assignee_user_soeid = normalize_str(row.get("assignee_user_soeid")) or None
            assignee = normalize_str(row.get("assignee")) or None
            window_name = normalize_str(row.get("window_name"))
            window_id = normalize_str(row.get("window_id")) or None
            if window_name:
                window = _window_by_name(session, space_ctx, window_name)
                if not window:
                    raise ValueError(f"Row {idx}: window_name '{window_name}' does not exist")
                window_id = window.window_id
            elif window_id:
                get_window(session, window_id, space_ctx)
            duplicate_key = (
                work_item_type,
                work_item_id,
                normalized_month.isoformat(),
                assignee_user_soeid or "",
                team_id or "",
                window_id or "",
            )
            if duplicate_key in seen:
                raise ValueError(f"Row {idx}: duplicate allocation in CSV (strict-first policy)")
            seen.add(duplicate_key)
            existing_query = (
                allocation_query(session, space_ctx)
                .filter(ResourceAllocation.work_item_type == work_item_type)
                .filter(ResourceAllocation.work_item_id == work_item_id)
                .filter(allocation_month_expr() == normalized_month)
            )
            if assignee_user_soeid:
                existing_query = existing_query.filter(ResourceAllocation.assignee_user_soeid == assignee_user_soeid)
            else:
                existing_query = existing_query.filter(ResourceAllocation.assignee_user_soeid.is_(None)).filter(ResourceAllocation.team_id == team_id)
            if window_id:
                existing_query = existing_query.filter(ResourceAllocation.window_id == window_id)
            else:
                existing_query = existing_query.filter(ResourceAllocation.window_id.is_(None))
            existing = existing_query.first()
            records.append(
                {
                    "existing": existing,
                    "work_item_type": work_item_type,
                    "work_item_id": work_item_id,
                    "month_start": normalized_month,
                    "hours": hours,
                    "fte_months": fte_months,
                    "assignee": assignee,
                    "assignee_user_soeid": assignee_user_soeid,
                    "team_id": team_id,
                    "window_id": window_id,
                }
            )
            if existing:
                updated += 1
            else:
                created += 1
        except (TypeError, ValueError) as exc:
            errors.append(str(exc))
    if dry_run or (atomic and errors):
        return {
            "created": 0 if atomic and errors else created,
            "updated": 0 if atomic and errors else updated,
            "errors": errors,
            "total_rows": len(rows),
            "dry_run": _bool_query(dry_run),
        }
    now = datetime.now(timezone.utc)
    try:
        for record in records:
            existing = record["existing"]
            if existing:
                existing.assignee = record["assignee"]
                existing.assignee_user_soeid = record["assignee_user_soeid"]
                existing.team_id = record["team_id"]
                existing.week_start = record["month_start"]
                existing.month_start = record["month_start"]
                existing.hours = record["hours"]
                existing.fte_months = record["fte_months"]
                existing.window_id = record["window_id"]
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(
                    ResourceAllocation(
                        space_id=space_ctx.space_id,
                        work_item_type=record["work_item_type"],
                        work_item_id=record["work_item_id"],
                        assignee=record["assignee"],
                        assignee_user_soeid=record["assignee_user_soeid"],
                        team_id=record["team_id"],
                        week_start=record["month_start"],
                        month_start=record["month_start"],
                        hours=record["hours"],
                        fte_months=record["fte_months"],
                        window_id=record["window_id"],
                        created_at=now,
                        updated_at=now,
                    )
                )
        commit_planning_mutation(session, space_ctx)
    except Exception as exc:
        session.rollback()
        errors.append(str(exc))
        if atomic:
            created = updated = 0
    return {"created": created, "updated": updated, "errors": errors, "total_rows": len(rows), "dry_run": False}


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


@router.get("/planning/windows/export")
def export_planning_windows(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    rows = [
        {
            "window_name": row.name,
            "start_date": row.start_date.isoformat(),
            "end_date": row.end_date.isoformat(),
        }
        for row in window_query(session, space_ctx).order_by(PlanningWindow.start_date.asc(), PlanningWindow.name.asc()).all()
    ]
    headers = {"Content-Disposition": 'attachment; filename="planning-windows.csv"'}
    return StreamingResponse(_write_csv(_WINDOW_EXPORT_FIELDNAMES, rows), media_type="text/csv", headers=headers)


@router.post("/planning/windows/import")
def import_planning_windows(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    dry_run: bool = False,
    atomic: bool = False,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"created": 0, "updated": 0, "errors": errors, "total_rows": 0, "dry_run": _bool_query(dry_run)}
    records = []
    seen = set()
    created = updated = 0
    for idx, row in enumerate(rows, start=2):
        name = normalize_str(row.get("window_name") or row.get("name"))
        if not name:
            errors.append(f"Row {idx}: window_name is required")
            continue
        key = name.lower()
        if key in seen:
            errors.append(f"Row {idx}: duplicate window_name '{name}' in CSV (strict-first policy)")
            continue
        seen.add(key)
        try:
            start_date = parse_date(row.get("start_date"))
            end_date = parse_date(row.get("end_date"))
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue
        if start_date is None or end_date is None:
            errors.append(f"Row {idx}: start_date and end_date are required")
            continue
        if end_date < start_date:
            errors.append(f"Row {idx}: end_date must be on or after start_date")
            continue
        existing = _window_by_name(session, space_ctx, name)
        records.append((existing, name, start_date, end_date))
        if existing:
            updated += 1
        else:
            created += 1
    if dry_run or (atomic and errors):
        return {
            "created": 0 if atomic and errors else created,
            "updated": 0 if atomic and errors else updated,
            "errors": errors,
            "total_rows": len(rows),
            "dry_run": _bool_query(dry_run),
        }
    now = datetime.now(timezone.utc)
    try:
        for existing, name, start_date, end_date in records:
            if existing:
                existing.start_date = start_date
                existing.end_date = end_date
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(
                    PlanningWindow(
                        space_id=space_ctx.space_id,
                        name=name,
                        start_date=start_date,
                        end_date=end_date,
                        created_at=now,
                        updated_at=now,
                    )
                )
        commit_planning_mutation(session, space_ctx)
    except Exception as exc:
        session.rollback()
        errors.append(str(exc))
        if atomic:
            created = updated = 0
    return {"created": created, "updated": updated, "errors": errors, "total_rows": len(rows), "dry_run": False}


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
