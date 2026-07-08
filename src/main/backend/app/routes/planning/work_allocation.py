from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...auth.auth import hash_bootstrap_password
from ...deps import current_space as current_space_dep, current_user as current_user_dep, get_db, require_space_role
from ...models import Project, ResourceAllocation, Solution, SpaceMembership, Task, Team, User
from ...schemas.planning import (
    WorkAllocationAssignmentCreate,
    WorkAllocationAssignmentRead,
    WorkAllocationAssignmentUpdate,
    WorkAllocationBoardRead,
    WorkAllocationPersonCreate,
    WorkAllocationPersonRead,
    WorkAllocationPersonUpdate,
    WorkAllocationProjectRead,
    WorkAllocationSolutionRead,
    WorkAllocationTaskCreate,
    WorkAllocationTaskRead,
    WorkAllocationTaskUpdate,
    WorkAllocationTeamCreate,
    WorkAllocationTeamRead,
    WorkAllocationTeamUpdate,
)
from ...services.planning_report_pdf import build_work_allocation_report_pdf
from ...services.planning_work_allocation import (
    WORK_ALLOCATION_DEFAULT_ASSIGNEE,
    WORK_ALLOCATION_DOMAIN,
    WORK_ALLOCATION_PROJECT_PREFIX,
    active_person_by_soeid,
    active_space_user_query,
    board_solution,
    ensure_membership,
    month_from_token,
    month_token,
    next_available_soeid,
    planning_task_query,
    task_fte_months,
    team_name_to_id_map,
)
from ...services.spaces import SpaceContext
from ...services.smart_cache import cached_call, invalidate_space, make_scope_token
from ...services.user_admin_guards import ensure_actor_can_modify_user, ensure_user_can_be_deactivated
from ...utils.enums import TaskStatus
from .common import (
    _HOURS_PER_FTE_MONTH,
    _PLANNING_LIST_TTL_SECONDS,
    active_team,
    allocation_for_board_payload,
    allocation_month_expr,
    allocation_query,
    commit_planning_mutation,
    ensure_work_allocation_assignment_available,
    existing_work_allocation_assignment,
    get_allocation,
    person_payload,
    raise_on_unique_allocation_conflict,
    raise_team_name_conflict,
    raise_team_rename_conflict,
    resolve_work_allocation_assignee,
    role_scope,
    task_payload,
    team_query,
    work_allocation_revival_query,
)


router = APIRouter()

_CLOSED_TASK_STATUSES = {TaskStatus.complete, TaskStatus.abandoned}
_WORK_ALLOCATION_TYPES = {"project", "solution", "task"}


def _nonblank_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is required")
    return text


def _fte_from_hours(hours: int | float | None, *, fallback: float = 0.25) -> float:
    numeric = float(hours or 0)
    if numeric <= 0:
        return round(float(fallback), 3)
    return round(numeric / _HOURS_PER_FTE_MONTH, 3)


def _allocation_fte(row: ResourceAllocation) -> float:
    fte = float(row.fte_months or 0.0)
    if fte <= 0 and row.hours:
        fte = float(row.hours or 0) / _HOURS_PER_FTE_MONTH
    return round(max(fte, 0.0), 3)


def _active_portfolio_project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(~Project.project_name.like(f"{WORK_ALLOCATION_PROJECT_PREFIX} [%"))
    )


def _active_portfolio_solution_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space_ctx.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(~Project.project_name.like(f"{WORK_ALLOCATION_PROJECT_PREFIX} [%"))
    )


def _solution_effort_map(
    solutions: list[Solution],
    tasks_by_solution: dict[str, list[Task]],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for solution in solutions:
        if int(solution.capacity_hours or 0) > 0:
            values[solution.solution_id] = _fte_from_hours(solution.capacity_hours)
            continue
        active_task_hours = 0
        for task in tasks_by_solution.get(solution.solution_id, []):
            if task.status in _CLOSED_TASK_STATUSES:
                continue
            active_task_hours += int(task.capacity_hours or task.estimate_hours or 0)
        values[solution.solution_id] = _fte_from_hours(active_task_hours)
    return values


def _project_effort_map(
    projects: list[Project],
    solutions_by_project: dict[str, list[Solution]],
    solution_fte: dict[str, float],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for project in projects:
        total = sum(solution_fte.get(solution.solution_id, 0.0) for solution in solutions_by_project.get(project.project_id, []))
        values[project.project_id] = round(total if total > 0 else 0.25, 3)
    return values


def _allocated_solution_fte_by_project(
    allocations: list[ResourceAllocation],
    solution_project_map: dict[str, str],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for allocation in allocations:
        if allocation.work_item_type != "solution":
            continue
        project_id = solution_project_map.get(allocation.work_item_id)
        if not project_id:
            continue
        values[project_id] = round(values.get(project_id, 0.0) + _allocation_fte(allocation), 3)
    return values


def _allocated_solution_fte_by_solution(allocations: list[ResourceAllocation]) -> dict[str, float]:
    values: dict[str, float] = {}
    for allocation in allocations:
        if allocation.work_item_type != "solution":
            continue
        values[allocation.work_item_id] = round(values.get(allocation.work_item_id, 0.0) + _allocation_fte(allocation), 3)
    return values


def _capped_allocated_solution_fte_by_project(
    allocated_solution_fte: dict[str, float],
    solution_project_map: dict[str, str],
    solution_fte: dict[str, float],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for solution_id, allocated_fte in allocated_solution_fte.items():
        project_id = solution_project_map.get(solution_id)
        if not project_id:
            continue
        planned_fte = solution_fte.get(solution_id, 0.0)
        values[project_id] = round(values.get(project_id, 0.0) + min(max(allocated_fte, 0.0), planned_fte), 3)
    return values


def _resolve_assignment_work_item(payload: WorkAllocationAssignmentCreate) -> tuple[str, str]:
    work_item_type = str(payload.work_item_type or "task").strip().lower()
    if work_item_type not in _WORK_ALLOCATION_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="work_item_type must be project, solution, or task")
    work_item_id = str(payload.work_item_id or payload.task_id or "").strip()
    if not work_item_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="work_item_id is required")
    return work_item_type, work_item_id


def _get_project_or_404(session: Session, space_ctx: SpaceContext, project_id: str) -> Project:
    project = _active_portfolio_project_query(session, space_ctx).filter(Project.project_id == project_id).first()
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _get_solution_or_404(session: Session, space_ctx: SpaceContext, solution_id: str) -> Solution:
    solution = _active_portfolio_solution_query(session, space_ctx).filter(Solution.solution_id == solution_id).first()
    if not solution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Solution not found")
    return solution


def _work_item_fte(session: Session, space_ctx: SpaceContext, work_item_type: str, work_item_id: str) -> float:
    if work_item_type == "task":
        task = planning_task_query(session, space_ctx).filter(Task.task_id == work_item_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task_fte_months(task, hours_per_fte_month=_HOURS_PER_FTE_MONTH)

    if work_item_type == "solution":
        solution = _get_solution_or_404(session, space_ctx, work_item_id)
        tasks = (
            planning_task_query(session, space_ctx)
            .filter(Task.solution_id == solution.solution_id)
            .all()
        )
        return _solution_effort_map([solution], {solution.solution_id: tasks})[solution.solution_id]

    project = _get_project_or_404(session, space_ctx, work_item_id)
    solutions = _active_portfolio_solution_query(session, space_ctx).filter(Solution.project_id == project.project_id).all()
    solution_ids = [row.solution_id for row in solutions]
    tasks_by_solution: dict[str, list[Task]] = {solution_id: [] for solution_id in solution_ids}
    if solution_ids:
        for task in planning_task_query(session, space_ctx).filter(Task.solution_id.in_(solution_ids)).all():
            tasks_by_solution.setdefault(task.solution_id, []).append(task)
    solution_fte = _solution_effort_map(solutions, tasks_by_solution)
    return _project_effort_map([project], {project.project_id: solutions}, solution_fte)[project.project_id]


def _solution_allocation_total(
    session: Session,
    space_ctx: SpaceContext,
    solution_id: str,
    month_start,
    *,
    exclude_allocation_id: str | None = None,
) -> float:
    query = (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "solution")
        .filter(ResourceAllocation.work_item_id == solution_id)
        .filter(allocation_month_expr() == month_start)
    )
    if exclude_allocation_id:
        query = query.filter(ResourceAllocation.allocation_id != exclude_allocation_id)
    return round(sum(_allocation_fte(row) for row in query.all()), 3)


def _project_solution_allocation_total(
    session: Session,
    space_ctx: SpaceContext,
    project_id: str,
    month_start,
) -> float:
    solutions = (
        _active_portfolio_solution_query(session, space_ctx)
        .filter(Solution.project_id == project_id)
        .all()
    )
    solution_ids = [row.solution_id for row in solutions]
    if not solution_ids:
        return 0.0
    tasks_by_solution: dict[str, list[Task]] = {solution_id: [] for solution_id in solution_ids}
    for task in planning_task_query(session, space_ctx).filter(Task.solution_id.in_(solution_ids)).all():
        tasks_by_solution.setdefault(task.solution_id, []).append(task)
    solution_fte = _solution_effort_map(solutions, tasks_by_solution)
    rows = (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "solution")
        .filter(ResourceAllocation.work_item_id.in_(solution_ids))
        .filter(allocation_month_expr() == month_start)
        .all()
    )
    allocated_solution_fte = _allocated_solution_fte_by_solution(rows)
    return round(
        sum(min(allocated_solution_fte.get(solution_id, 0.0), solution_fte.get(solution_id, 0.0)) for solution_id in solution_ids),
        3,
    )


def _project_residual_fte(session: Session, space_ctx: SpaceContext, project_id: str, month_start) -> float:
    project_fte = _work_item_fte(session, space_ctx, "project", project_id)
    child_fte = _project_solution_allocation_total(session, space_ctx, project_id, month_start)
    return round(max(project_fte - child_fte, 0.0), 3)


def _sync_project_residual_allocation(
    session: Session,
    space_ctx: SpaceContext,
    project_id: str,
    month_start,
) -> None:
    parent_rows = (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "project")
        .filter(ResourceAllocation.work_item_id == project_id)
        .filter(allocation_month_expr() == month_start)
        .all()
    )
    if not parent_rows:
        return
    residual = _project_residual_fte(session, space_ctx, project_id, month_start)
    hours = max(int(round(residual * _HOURS_PER_FTE_MONTH)), 0)
    now = datetime.now(timezone.utc)
    for row in parent_rows:
        row.fte_months = residual
        row.hours = hours
        row.updated_at = now
        session.add(row)


def _space_user_membership_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(User)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
    )


def _invalidate_user_caches_for_user_memberships(session: Session, user_ids: set[str]) -> None:
    if not user_ids:
        return
    rows = (
        session.query(SpaceMembership.space_id)
        .filter(SpaceMembership.user_id.in_(sorted(user_ids)))
        .filter(SpaceMembership.deleted_at.is_(None))
        .distinct()
        .all()
    )
    for row in rows:
        space_id = row[0] if isinstance(row, tuple) else getattr(row, "space_id", None)
        if space_id:
            invalidate_space(space_id, ["users"])


def _work_allocation_board_payload(
    session: Session,
    space_ctx: SpaceContext,
    *,
    month_start,
    search: str | None = None,
) -> WorkAllocationBoardRead:
    teams = team_query(session, space_ctx).order_by(Team.name.asc()).all()
    team_map = team_name_to_id_map(session, space_ctx)
    people = active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()

    project_query = _active_portfolio_project_query(session, space_ctx)
    solution_query = _active_portfolio_solution_query(session, space_ctx)
    if search:
        term = f"%{search.strip().lower()}%"
        direct_project_ids = [
            row[0]
            for row in _active_portfolio_project_query(session, space_ctx)
            .filter(func.lower(Project.project_name).like(term))
            .with_entities(Project.project_id)
            .all()
        ]
        solution_project_ids = [
            row[0]
            for row in _active_portfolio_solution_query(session, space_ctx)
            .filter(func.lower(Solution.solution_name).like(term))
            .with_entities(Solution.project_id)
            .distinct()
            .all()
        ]
        matching_project_ids = sorted(set(direct_project_ids + solution_project_ids))
        project_query = project_query.filter(Project.project_id.in_(matching_project_ids or [""]))
        solution_query = solution_query.filter(Solution.project_id.in_(matching_project_ids or [""]))

    projects = project_query.order_by(Project.priority.asc(), Project.created_at.asc()).all()
    project_ids = [project.project_id for project in projects]
    solutions = (
        solution_query
        .filter(Solution.project_id.in_(project_ids or [""]))
        .order_by(Solution.priority.asc(), Solution.created_at.asc())
        .all()
    )
    solution_ids = [solution.solution_id for solution in solutions]

    tasks_by_solution: dict[str, list[Task]] = {solution_id: [] for solution_id in solution_ids}
    if solution_ids:
        for task in planning_task_query(session, space_ctx).filter(Task.solution_id.in_(solution_ids)).all():
            tasks_by_solution.setdefault(task.solution_id, []).append(task)

    solutions_by_project: dict[str, list[Solution]] = {project_id: [] for project_id in project_ids}
    for solution in solutions:
        solutions_by_project.setdefault(solution.project_id, []).append(solution)

    solution_fte = _solution_effort_map(solutions, tasks_by_solution)
    project_fte = _project_effort_map(projects, solutions_by_project, solution_fte)
    solution_project_map = {solution.solution_id: solution.project_id for solution in solutions}

    allocations: list[ResourceAllocation] = []
    work_item_ids = project_ids + solution_ids
    if work_item_ids:
        allocations = (
            allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type.in_(["project", "solution"]))
            .filter(ResourceAllocation.work_item_id.in_(work_item_ids))
            .filter(allocation_month_expr() == month_start)
            .order_by(ResourceAllocation.created_at.asc())
            .all()
        )

    allocated_solution_by_solution = _allocated_solution_fte_by_solution(allocations)
    allocated_solution_by_project = _allocated_solution_fte_by_project(allocations, solution_project_map)
    capped_allocated_solution_by_project = _capped_allocated_solution_fte_by_project(
        allocated_solution_by_solution,
        solution_project_map,
        solution_fte,
    )

    return WorkAllocationBoardRead(
        teams=[WorkAllocationTeamRead(id=row.team_id, name=row.name) for row in teams],
        people=[person_payload(row, team_map) for row in people],
        projects=[
            WorkAllocationProjectRead(
                id=row.project_id,
                title=row.project_name,
                status=row.status.value if hasattr(row.status, "value") else str(row.status),
                fte_months=project_fte[row.project_id],
                allocated_solution_fte_months=allocated_solution_by_project.get(row.project_id, 0.0),
                residual_fte_months=round(max(project_fte[row.project_id] - capped_allocated_solution_by_project.get(row.project_id, 0.0), 0.0), 3),
                solution_count=len(solutions_by_project.get(row.project_id, [])),
            )
            for row in projects
        ],
        solutions=[
            WorkAllocationSolutionRead(
                id=row.solution_id,
                project_id=row.project_id,
                title=row.solution_name,
                version=row.version,
                status=row.status.value if hasattr(row.status, "value") else str(row.status),
                fte_months=solution_fte[row.solution_id],
                allocated_fte_months=allocated_solution_by_solution.get(row.solution_id, 0.0),
                remaining_fte_months=round(max(solution_fte[row.solution_id] - allocated_solution_by_solution.get(row.solution_id, 0.0), 0.0), 3),
            )
            for row in solutions
        ],
        allocations=[allocation_for_board_payload(row, space_ctx, session) for row in allocations],
    )


@router.get("/planning/work-allocation/board", response_model=WorkAllocationBoardRead)
def get_work_allocation_board(
    month: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationBoardRead:
    month_start = month_from_token(month or month_token(None))
    normalized_search = (search or "").strip()
    return cached_call(
        endpoint="planning:work-allocation:board",
        params={
            "month": month_token(month_start),
            "search": normalized_search.lower(),
        },
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=role_scope(space_ctx),
        ttl_seconds=_PLANNING_LIST_TTL_SECONDS,
        scope_tokens=[
            make_scope_token("planning", space_ctx.space_id),
            make_scope_token("projects", space_ctx.space_id),
            make_scope_token("solutions", space_ctx.space_id),
            make_scope_token("tasks", space_ctx.space_id),
            make_scope_token("teams", space_ctx.space_id),
            make_scope_token("users", space_ctx.space_id),
        ],
        loader=lambda: _work_allocation_board_payload(
            session,
            space_ctx,
            month_start=month_start,
            search=normalized_search or None,
        ),
    )


@router.get("/planning/work-allocation/teams", response_model=List[WorkAllocationTeamRead])
def list_work_allocation_teams(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationTeamRead]:
    rows = team_query(session, space_ctx).order_by(Team.name.asc()).all()
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
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationTeamRead:
    name = _nonblank_text(payload.name, field_name="Team name")

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
        commit_planning_mutation(
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
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("teams", "planning"),
        refresh=row,
        on_integrity_error=raise_team_name_conflict,
    )
    return WorkAllocationTeamRead(id=row.team_id, name=row.name)


@router.patch("/planning/work-allocation/teams/{team_id}", response_model=WorkAllocationTeamRead)
def update_work_allocation_team(
    team_id: str,
    payload: WorkAllocationTeamUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationTeamRead:
    row = active_team(session, team_id, space_ctx)
    next_name = _nonblank_text(payload.name, field_name="Team name") if payload.name is not None else None
    affected_user_ids: set[str] = set()
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
        for user in _space_user_membership_query(session, space_ctx).filter(User.team_tag == old_name).all():
            user.team_tag = next_name
            session.add(user)
            affected_user_ids.add(user.user_id)
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("teams", "users", "planning"),
        refresh=row,
        on_integrity_error=raise_team_rename_conflict,
    )
    _invalidate_user_caches_for_user_memberships(session, affected_user_ids)
    return WorkAllocationTeamRead(id=row.team_id, name=row.name)


@router.delete("/planning/work-allocation/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_team(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    row = active_team(session, team_id, space_ctx)
    now = datetime.now(timezone.utc)
    old_name = row.name
    affected_user_ids: set[str] = set()
    row.deleted_at = now
    session.add(row)
    for user in _space_user_membership_query(session, space_ctx).filter(User.team_tag == old_name).all():
        user.team_tag = None
        user.updated_at = now
        session.add(user)
        affected_user_ids.add(user.user_id)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("teams", "users", "planning"),
    )
    _invalidate_user_caches_for_user_memberships(session, affected_user_ids)
    return None


@router.get("/planning/work-allocation/people", response_model=List[WorkAllocationPersonRead])
def list_work_allocation_people(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationPersonRead]:
    team_map = team_name_to_id_map(session, space_ctx)
    rows = active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()
    return [person_payload(row, team_map) for row in rows]


@router.post(
    "/planning/work-allocation/people",
    response_model=WorkAllocationPersonRead,
    status_code=status.HTTP_201_CREATED,
)
def create_work_allocation_person(
    payload: WorkAllocationPersonCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationPersonRead:
    name = _nonblank_text(payload.name, field_name="Person name")
    team = active_team(session, payload.team_id, space_ctx) if payload.team_id else None
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
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("users", "planning"),
        refresh=row,
    )
    team_map = team_name_to_id_map(session, space_ctx)
    return person_payload(row, team_map)


@router.patch("/planning/work-allocation/people/{person_id}", response_model=WorkAllocationPersonRead)
def update_work_allocation_person(
    person_id: str,
    payload: WorkAllocationPersonUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationPersonRead:
    row = active_person_by_soeid(session, person_id, space_ctx)
    ensure_actor_can_modify_user(actor=current_user, target=row)
    updates = payload.model_dump(exclude_unset=True)

    if "name" in updates:
        row.display_name = _nonblank_text(updates.get("name"), field_name="Person name")

    if "team_id" in updates:
        next_team_id = updates.get("team_id")
        team = active_team(session, next_team_id, space_ctx) if next_team_id else None
        row.team_tag = team.name if team else None

    if "capacity_fte_months" in updates and updates.get("capacity_fte_months") is not None:
        cap = max(float(updates["capacity_fte_months"]), 0.0)
        row.capacity_fte_month = round(cap, 3)
        row.capacity_hours = max(int(round(cap * 40.0)), 0)

    if "active" in updates and updates.get("active") is not None:
        if row.is_active and not bool(updates["active"]):
            ensure_user_can_be_deactivated(session, row)
        row.is_active = bool(updates["active"])

    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("users", "planning"),
        refresh=row,
    )
    team_map = team_name_to_id_map(session, space_ctx)
    return person_payload(row, team_map)


@router.delete("/planning/work-allocation/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_person(
    person_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    row = active_person_by_soeid(session, person_id, space_ctx)
    ensure_actor_can_modify_user(actor=current_user, target=row)
    ensure_user_can_be_deactivated(session, row)
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
    commit_planning_mutation(
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
        query = query.filter(func.lower(Task.task_name).like(term))
    tasks = query.order_by(Task.created_at.asc()).all()
    task_ids = [task.task_id for task in tasks]
    assigned_ids: set[str] = set()
    if task_ids:
        for row in (
            allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "task")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(allocation_month_expr() == month_start)
            .all()
        ):
            assigned_ids.add(row.work_item_id)
    return [task_payload(task, assigned_ids) for task in tasks]


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
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationTaskRead:
    solution = board_solution(session, space_ctx)
    query = planning_task_query(session, space_ctx).filter(Task.solution_id == solution.solution_id)
    title = _nonblank_text(payload.title, field_name="Task title")
    conflict = query.filter(func.lower(Task.task_name) == title.lower()).first()
    if conflict:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists")
    raw_fte = payload.fte_months if payload.fte_months is not None else 0.25
    fte = round(max(float(raw_fte), 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
    now = datetime.now(timezone.utc)
    row = Task(
        space_id=space_ctx.space_id,
        project_id=solution.project_id,
        solution_id=solution.solution_id,
        task_name=title,
        status=TaskStatus.to_do,
        priority=3,
        assignee=WORK_ALLOCATION_DEFAULT_ASSIGNEE,
        estimate_hours=hours,
        capacity_hours=hours,
        blocked=False,
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("tasks", "planning"),
        refresh=row,
    )
    month_start = month_from_token(month or month_token(None))
    assigned_ids: set[str] = set()
    if (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "task")
        .filter(ResourceAllocation.work_item_id == row.task_id)
        .filter(allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.task_id)
    return task_payload(row, assigned_ids)


@router.patch("/planning/work-allocation/tasks/{task_id}", response_model=WorkAllocationTaskRead)
def update_work_allocation_task(
    task_id: str,
    month: Optional[str] = Query(None),
    payload: WorkAllocationTaskUpdate = ...,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationTaskRead:
    query = planning_task_query(session, space_ctx)
    row = query.filter(Task.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title is required")
        conflict = (
            query.filter(Task.solution_id == row.solution_id)
            .filter(func.lower(Task.task_name) == title.lower())
            .filter(Task.task_id != task_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists")
        row.task_name = title
    if payload.fte_months is not None:
        fte = round(max(float(payload.fte_months), 0.05), 3)
        hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 1)
        row.estimate_hours = hours
        row.capacity_hours = hours
    row.updated_at = datetime.now(timezone.utc)
    session.add(row)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("tasks", "planning"),
        refresh=row,
    )
    month_start = month_from_token(month or month_token(None))
    assigned_ids: set[str] = set()
    if (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "task")
        .filter(ResourceAllocation.work_item_id == row.task_id)
        .filter(allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.task_id)
    return task_payload(row, assigned_ids)


@router.delete("/planning/work-allocation/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_task(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    query = planning_task_query(session, space_ctx)
    row = query.filter(Task.task_id == task_id).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    for alloc in (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "task")
        .filter(ResourceAllocation.work_item_id == task_id)
        .all()
    ):
        alloc.deleted_at = now
        alloc.updated_at = now
        session.add(alloc)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("tasks", "planning"),
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
    project_ids = [row.project_id for row in _active_portfolio_project_query(session, space_ctx).all()]
    solution_ids = [row.solution_id for row in _active_portfolio_solution_query(session, space_ctx).all()]
    task_ids = [row.task_id for row in planning_task_query(session, space_ctx).all()]
    work_item_ids = project_ids + solution_ids + task_ids
    if not work_item_ids:
        return []
    rows = (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type.in_(["project", "solution", "task"]))
        .filter(ResourceAllocation.work_item_id.in_(work_item_ids))
        .filter(allocation_month_expr() == month_start)
        .order_by(ResourceAllocation.created_at.asc())
        .all()
    )
    return [allocation_for_board_payload(row, space_ctx, session) for row in rows]


@router.get("/planning/work-allocation/report.pdf")
def download_work_allocation_report_pdf(
    month: Optional[str] = Query(None),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> StreamingResponse:
    month_start = month_from_token(month or month_token(None))
    month_token_value = month_token(month_start)

    team_rows = team_query(session, space_ctx).order_by(Team.name.asc()).all()
    team_map = team_name_to_id_map(session, space_ctx)
    people_rows = active_space_user_query(session, space_ctx).order_by(User.display_name.asc()).all()
    people_payload = [person_payload(row, team_map).model_dump() for row in people_rows]

    task_query = planning_task_query(session, space_ctx)
    task_rows = task_query.order_by(Task.task_name.asc()).all()
    task_payload_rows = [
        {
            "id": row.task_id,
            "title": row.task_name,
            "fte_months": task_fte_months(row, hours_per_fte_month=_HOURS_PER_FTE_MONTH),
        }
        for row in task_rows
    ]
    task_ids = [row.task_id for row in task_rows]
    allocation_rows: list[ResourceAllocation] = []
    if task_ids:
        allocation_rows = (
            allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "task")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(allocation_month_expr() == month_start)
            .order_by(ResourceAllocation.created_at.asc())
            .all()
        )

    allocation_payload_rows = [
        allocation_for_board_payload(row, space_ctx, session).model_dump()
        for row in allocation_rows
    ]
    pdf_bytes = build_work_allocation_report_pdf(
        month_token=month_token_value,
        space_name=space_ctx.space_name,
        teams=[{"id": row.team_id, "name": row.name} for row in team_rows],
        people=people_payload,
        tasks=task_payload_rows,
        allocations=allocation_payload_rows,
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
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationAssignmentRead:
    month_start = month_from_token(payload.month)
    work_item_type, work_item_id = _resolve_assignment_work_item(payload)
    parent_project_id: str | None = None
    if work_item_type == "project":
        _get_project_or_404(session, space_ctx, work_item_id)
        parent_project_id = work_item_id
    elif work_item_type == "solution":
        solution = _get_solution_or_404(session, space_ctx, work_item_id)
        parent_project_id = solution.project_id
    else:
        task = planning_task_query(session, space_ctx).filter(Task.task_id == work_item_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    assignee_user_soeid, assignee_name, team_id = resolve_work_allocation_assignee(
        session, payload.assignee_type, payload.assignee_id, space_ctx
    )
    existing_assignment = existing_work_allocation_assignment(
        session,
        space_ctx,
        work_item_type,
        work_item_id,
        month_start,
        assignee_user_soeid,
        team_id,
    )
    if existing_assignment:
        return allocation_for_board_payload(existing_assignment, space_ctx, session)
    ensure_work_allocation_assignment_available(
        session,
        space_ctx,
        work_item_type,
        work_item_id,
        month_start,
        assignee_user_soeid,
        team_id,
    )

    fte = payload.fte_months_allocated
    if work_item_type == "project":
        fte = _project_residual_fte(session, space_ctx, work_item_id, month_start)
    elif work_item_type == "solution" and fte is None:
        fte = round(max(_work_item_fte(session, space_ctx, "solution", work_item_id) - _solution_allocation_total(session, space_ctx, work_item_id, month_start), 0.05), 3)
    elif fte is None:
        fte = _work_item_fte(session, space_ctx, work_item_type, work_item_id)
    fte = round(max(float(fte), 0.0 if work_item_type == "project" else 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 0 if work_item_type == "project" else 1)
    now = datetime.now(timezone.utc)

    revive_row = work_allocation_revival_query(
        session,
        space_ctx,
        work_item_type,
        work_item_id,
        month_start,
        assignee_user_soeid,
        team_id,
    ).first()
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
        if parent_project_id and work_item_type == "solution":
            session.flush()
            _sync_project_residual_allocation(session, space_ctx, parent_project_id, month_start)
        commit_planning_mutation(
            session,
            space_ctx,
            refresh=revive_row,
            on_integrity_error=raise_on_unique_allocation_conflict,
        )
        return allocation_for_board_payload(revive_row, space_ctx, session)

    row = ResourceAllocation(
        space_id=space_ctx.space_id,
        work_item_type=work_item_type,
        work_item_id=work_item_id,
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
    if parent_project_id and work_item_type == "solution":
        session.flush()
        _sync_project_residual_allocation(session, space_ctx, parent_project_id, month_start)
    commit_planning_mutation(
        session,
        space_ctx,
        refresh=row,
        on_integrity_error=raise_on_unique_allocation_conflict,
    )
    return allocation_for_board_payload(row, space_ctx, session)


@router.patch(
    "/planning/work-allocation/allocations/{allocation_id}",
    response_model=WorkAllocationAssignmentRead,
)
def update_work_allocation_allocation(
    allocation_id: str,
    payload: WorkAllocationAssignmentUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationAssignmentRead:
    row = get_allocation(session, allocation_id, space_ctx)
    if row.work_item_type not in _WORK_ALLOCATION_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Allocation is not a planning board assignment")

    month_start = row.month_start or (row.week_start.replace(day=1) if row.week_start else None)
    if month_start is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Allocation month is missing")

    parent_project_id: str | None = None
    if row.work_item_type == "project":
        _get_project_or_404(session, space_ctx, row.work_item_id)
        parent_project_id = row.work_item_id
    elif row.work_item_type == "solution":
        solution = _get_solution_or_404(session, space_ctx, row.work_item_id)
        parent_project_id = solution.project_id
    else:
        task = planning_task_query(session, space_ctx).filter(Task.task_id == row.work_item_id).first()
        if not task:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    assignee_user_soeid, assignee_name, team_id = resolve_work_allocation_assignee(
        session, payload.assignee_type, payload.assignee_id, space_ctx
    )
    ensure_work_allocation_assignment_available(
        session,
        space_ctx,
        row.work_item_type,
        row.work_item_id,
        month_start,
        assignee_user_soeid,
        team_id,
        exclude_allocation_id=row.allocation_id,
    )

    fte = payload.fte_months_allocated
    if row.work_item_type == "project":
        fte = _project_residual_fte(session, space_ctx, row.work_item_id, month_start)
    elif fte is None:
        fte = float(row.fte_months or 0.0)
        if fte <= 0:
            fte = _work_item_fte(session, space_ctx, row.work_item_type, row.work_item_id)
    fte = round(max(float(fte), 0.0 if row.work_item_type == "project" else 0.05), 3)
    hours = max(int(round(fte * _HOURS_PER_FTE_MONTH)), 0 if row.work_item_type == "project" else 1)
    now = datetime.now(timezone.utc)

    revive_row = work_allocation_revival_query(
        session,
        space_ctx,
        row.work_item_type,
        row.work_item_id,
        month_start,
        assignee_user_soeid,
        team_id,
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
        if parent_project_id and row.work_item_type == "solution":
            session.flush()
            _sync_project_residual_allocation(session, space_ctx, parent_project_id, month_start)
        commit_planning_mutation(
            session,
            space_ctx,
            refresh=revive_row,
            on_integrity_error=raise_on_unique_allocation_conflict,
        )
        return allocation_for_board_payload(revive_row, space_ctx, session)

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
    if parent_project_id and row.work_item_type == "solution":
        session.flush()
        _sync_project_residual_allocation(session, space_ctx, parent_project_id, month_start)
    commit_planning_mutation(
        session,
        space_ctx,
        refresh=row,
        on_integrity_error=raise_on_unique_allocation_conflict,
    )
    return allocation_for_board_payload(row, space_ctx, session)


@router.delete("/planning/work-allocation/allocations/{allocation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_work_allocation_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    row = get_allocation(session, allocation_id, space_ctx)
    parent_project_id: str | None = None
    month_start = row.month_start or (row.week_start.replace(day=1) if row.week_start else None)
    if row.work_item_type == "solution":
        solution = _get_solution_or_404(session, space_ctx, row.work_item_id)
        parent_project_id = solution.project_id
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    if parent_project_id and month_start is not None:
        session.flush()
        _sync_project_residual_allocation(session, space_ctx, parent_project_id, month_start)
    commit_planning_mutation(session, space_ctx)
    return None
