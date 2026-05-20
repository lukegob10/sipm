from datetime import datetime, timezone
from io import BytesIO
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...auth.auth import hash_bootstrap_password
from ...deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ...models import ResourceAllocation, SpaceMembership, Subcomponent, Team, User
from ...schemas.planning import (
    WorkAllocationAssignmentCreate,
    WorkAllocationAssignmentRead,
    WorkAllocationAssignmentUpdate,
    WorkAllocationBoardRead,
    WorkAllocationPersonCreate,
    WorkAllocationPersonRead,
    WorkAllocationPersonUpdate,
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
from ...services.user_admin_guards import (
    ensure_actor_can_modify_user,
    ensure_user_can_be_deactivated,
)
from ...utils.enums import SubcomponentStatus
from .common import (
    _HOURS_PER_FTE_MONTH,
    _PLANNING_LIST_TTL_SECONDS,
    active_team,
    allocation_for_board_payload,
    allocation_month_expr,
    allocation_query,
    commit_planning_mutation,
    ensure_work_allocation_assignment_available,
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


def _nonblank_text(value: object, *, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field_name} is required"
        )
    return text


def _space_user_membership_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(User)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
    )


def _invalidate_user_caches_for_user_memberships(
    session: Session, user_ids: set[str]
) -> None:
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
    people = (
        active_space_user_query(session, space_ctx)
        .order_by(User.display_name.asc())
        .all()
    )
    task_query = planning_task_query(session, space_ctx)
    if search:
        term = f"%{search.strip().lower()}%"
        task_query = task_query.filter(
            func.lower(Subcomponent.subcomponent_name).like(term)
        )
    tasks = task_query.order_by(Subcomponent.created_at.asc()).all()
    task_ids = [task.subcomponent_id for task in tasks]
    allocations: list[ResourceAllocation] = []
    assigned_ids: set[str] = set()
    if task_ids:
        allocations = (
            allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .filter(allocation_month_expr() == month_start)
            .order_by(ResourceAllocation.created_at.asc())
            .all()
        )
        assigned_ids = {row.work_item_id for row in allocations}
    return WorkAllocationBoardRead(
        teams=[WorkAllocationTeamRead(id=row.team_id, name=row.name) for row in teams],
        people=[person_payload(row, team_map) for row in people],
        tasks=[task_payload(row, assigned_ids) for row in tasks],
        allocations=[
            allocation_for_board_payload(row, space_ctx, session) for row in allocations
        ],
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
            make_scope_token("subcomponents", space_ctx.space_id),
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


@router.get(
    "/planning/work-allocation/teams", response_model=List[WorkAllocationTeamRead]
)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Team already exists"
        )
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


@router.patch(
    "/planning/work-allocation/teams/{team_id}", response_model=WorkAllocationTeamRead
)
def update_work_allocation_team(
    team_id: str,
    payload: WorkAllocationTeamUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationTeamRead:
    row = active_team(session, team_id, space_ctx)
    next_name = (
        _nonblank_text(payload.name, field_name="Team name")
        if payload.name is not None
        else None
    )
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
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team name already exists",
            )
        old_name = row.name
        row.name = next_name
        for user in (
            _space_user_membership_query(session, space_ctx)
            .filter(User.team_tag == old_name)
            .all()
        ):
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


@router.delete(
    "/planning/work-allocation/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT
)
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
    for user in (
        _space_user_membership_query(session, space_ctx)
        .filter(User.team_tag == old_name)
        .all()
    ):
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


@router.get(
    "/planning/work-allocation/people", response_model=List[WorkAllocationPersonRead]
)
def list_work_allocation_people(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[WorkAllocationPersonRead]:
    team_map = team_name_to_id_map(session, space_ctx)
    rows = (
        active_space_user_query(session, space_ctx)
        .order_by(User.display_name.asc())
        .all()
    )
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
    raw_capacity = (
        payload.capacity_fte_months if payload.capacity_fte_months is not None else 1.0
    )
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


@router.patch(
    "/planning/work-allocation/people/{person_id}",
    response_model=WorkAllocationPersonRead,
)
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

    if (
        "capacity_fte_months" in updates
        and updates.get("capacity_fte_months") is not None
    ):
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


@router.delete(
    "/planning/work-allocation/people/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
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


@router.get(
    "/planning/work-allocation/tasks", response_model=List[WorkAllocationTaskRead]
)
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
    task_ids = [task.subcomponent_id for task in tasks]
    assigned_ids: set[str] = set()
    if task_ids:
        for row in (
            allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
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
    query = planning_task_query(session, space_ctx).filter(
        Subcomponent.solution_id == solution.solution_id
    )
    title = _nonblank_text(payload.title, field_name="Task title")
    conflict = query.filter(
        func.lower(Subcomponent.subcomponent_name) == title.lower()
    ).first()
    if conflict:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Task title already exists"
        )
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
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("subcomponents", "planning"),
        refresh=row,
    )
    month_start = month_from_token(month or month_token(None))
    assigned_ids: set[str] = set()
    if (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == row.subcomponent_id)
        .filter(allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.subcomponent_id)
    return task_payload(row, assigned_ids)


@router.patch(
    "/planning/work-allocation/tasks/{task_id}", response_model=WorkAllocationTaskRead
)
def update_work_allocation_task(
    task_id: str,
    month: Optional[str] = Query(None),
    payload: WorkAllocationTaskUpdate = ...,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> WorkAllocationTaskRead:
    query = planning_task_query(session, space_ctx)
    row = query.filter(Subcomponent.subcomponent_id == task_id).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Task title is required"
            )
        conflict = (
            query.filter(Subcomponent.solution_id == row.solution_id)
            .filter(func.lower(Subcomponent.subcomponent_name) == title.lower())
            .filter(Subcomponent.subcomponent_id != task_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task title already exists",
            )
        row.subcomponent_name = title
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
        cache_keys=("subcomponents", "planning"),
        refresh=row,
    )
    month_start = month_from_token(month or month_token(None))
    assigned_ids: set[str] = set()
    if (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == row.subcomponent_id)
        .filter(allocation_month_expr() == month_start)
        .first()
    ):
        assigned_ids.add(row.subcomponent_id)
    return task_payload(row, assigned_ids)


@router.delete(
    "/planning/work-allocation/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_work_allocation_task(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    query = planning_task_query(session, space_ctx)
    row = query.filter(Subcomponent.subcomponent_id == task_id).first()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    for alloc in (
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id == task_id)
        .all()
    ):
        alloc.deleted_at = now
        alloc.updated_at = now
        session.add(alloc)
    commit_planning_mutation(
        session,
        space_ctx,
        cache_keys=("subcomponents", "planning"),
    )
    return None


@router.get(
    "/planning/work-allocation/allocations",
    response_model=List[WorkAllocationAssignmentRead],
)
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
        allocation_query(session, space_ctx)
        .filter(ResourceAllocation.work_item_type == "subcomponent")
        .filter(ResourceAllocation.work_item_id.in_(task_ids))
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
    people_rows = (
        active_space_user_query(session, space_ctx)
        .order_by(User.display_name.asc())
        .all()
    )
    people_payload = [person_payload(row, team_map).model_dump() for row in people_rows]

    task_query = planning_task_query(session, space_ctx)
    task_rows = task_query.order_by(Subcomponent.subcomponent_name.asc()).all()
    task_payload_rows = [
        {
            "id": row.subcomponent_id,
            "title": row.subcomponent_name,
            "fte_months": task_fte_months(
                row, hours_per_fte_month=_HOURS_PER_FTE_MONTH
            ),
        }
        for row in task_rows
    ]
    task_ids = [row.subcomponent_id for row in task_rows]
    allocation_rows: list[ResourceAllocation] = []
    if task_ids:
        allocation_rows = (
            allocation_query(session, space_ctx)
            .filter(ResourceAllocation.work_item_type == "subcomponent")
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
    return StreamingResponse(
        BytesIO(pdf_bytes), media_type="application/pdf", headers=headers
    )


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
    task_query = planning_task_query(session, space_ctx)
    task = task_query.filter(Subcomponent.subcomponent_id == payload.task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    assignee_user_soeid, assignee_name, team_id = resolve_work_allocation_assignee(
        session, payload.assignee_type, payload.assignee_id, space_ctx
    )
    ensure_work_allocation_assignment_available(
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

    revive_row = work_allocation_revival_query(
        session,
        space_ctx,
        payload.task_id,
        month_start,
        assignee_user_soeid,
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
        commit_planning_mutation(
            session,
            space_ctx,
            refresh=revive_row,
            on_integrity_error=raise_on_unique_allocation_conflict,
        )
        return allocation_for_board_payload(revive_row, space_ctx, session)

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
    if row.work_item_type != "subcomponent":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allocation is not a planning task assignment",
        )

    month_start = row.month_start or (
        row.week_start.replace(day=1) if row.week_start else None
    )
    if month_start is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Allocation month is missing",
        )

    task = (
        planning_task_query(session, space_ctx)
        .filter(Subcomponent.subcomponent_id == row.work_item_id)
        .first()
    )
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Task not found"
        )

    assignee_user_soeid, assignee_name, team_id = resolve_work_allocation_assignee(
        session, payload.assignee_type, payload.assignee_id, space_ctx
    )
    ensure_work_allocation_assignment_available(
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

    revive_row = work_allocation_revival_query(
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
    commit_planning_mutation(
        session,
        space_ctx,
        refresh=row,
        on_integrity_error=raise_on_unique_allocation_conflict,
    )
    return allocation_for_board_payload(row, space_ctx, session)


@router.delete(
    "/planning/work-allocation/allocations/{allocation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_work_allocation_allocation(
    allocation_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> None:
    row = get_allocation(session, allocation_id, space_ctx)
    now = datetime.now(timezone.utc)
    row.deleted_at = now
    row.updated_at = now
    session.add(row)
    commit_planning_mutation(session, space_ctx)
    return None
