import math
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
    require_non_agent_write,
)
from ..models import SpaceMembership, Team, TeamMember, User
from ..schemas import TeamCreate, TeamRead, TeamUpdate, TeamMemberCreate, TeamMemberRead, TeamMemberUpdate
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token
from ..utils import MAX_DB_INTEGER

router = APIRouter()
_TEAMS_LIST_TTL_SECONDS = 20
_TEAMS_DETAIL_TTL_SECONDS = 30
_HOURS_PER_FTE_CAPACITY = 40.0


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _team_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Team)
        .filter(Team.deleted_at.is_(None))
        .filter(Team.space_id == space_ctx.space_id)
    )


def _member_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(TeamMember)
        .filter(TeamMember.deleted_at.is_(None))
        .filter(TeamMember.space_id == space_ctx.space_id)
    )


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
    sorted_user_ids = sorted(user_ids)
    membership_filter = or_(*(
        SpaceMembership.user_id.in_(sorted_user_ids[index:index + 500])
        for index in range(0, len(sorted_user_ids), 500)
    ))
    rows = (
        session.query(SpaceMembership.space_id)
        .filter(membership_filter)
        .filter(SpaceMembership.deleted_at.is_(None))
        .distinct()
        .all()
    )
    for row in rows:
        space_id = row[0] if isinstance(row, tuple) else getattr(row, "space_id", None)
        if space_id:
            invalidate_space(space_id, ["users"])


def _active_team(session: Session, team_id: str, space_ctx: SpaceContext) -> Team:
    team = (
        _team_query(session, space_ctx)
        .filter(Team.team_id == team_id)
        .first()
    )
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def _team_capacity_lock_query(session: Session, team_id: str, space_ctx: SpaceContext):
    # Locking the parent first serializes membership writes before capacity is summed.
    return (
        _team_query(session, space_ctx)
        .filter(Team.team_id == team_id)
        .with_for_update()
    )


def _lock_active_team(session: Session, team_id: str, space_ctx: SpaceContext) -> Team:
    with session.no_autoflush:
        team = _team_capacity_lock_query(session, team_id, space_ctx).one_or_none()
    if not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def _active_member(session: Session, member_id: str, team_id: str, space_ctx: SpaceContext) -> TeamMember:
    member = (
        _member_query(session, space_ctx)
        .filter(TeamMember.team_member_id == member_id)
        .filter(TeamMember.team_id == team_id)
        .first()
    )
    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team member not found")
    return member


def _checked_hours(value: int) -> int:
    hours = max(int(value), 0)
    if hours > MAX_DB_INTEGER:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Capacity is too large")
    return hours


def _fte_from_hours(hours: Optional[int]) -> float:
    return round(_checked_hours(hours or 0) / _HOURS_PER_FTE_CAPACITY, 3)


def _hours_from_fte(fte_month: Optional[float]) -> int:
    return _checked_hours(round(max(float(fte_month or 0.0), 0.0) * _HOURS_PER_FTE_CAPACITY))


def _is_team_name_conflict_integrity_error(exc: IntegrityError) -> bool:
    text = " ".join(
        [
            str(exc),
            str(getattr(exc, "orig", "")),
            str(getattr(exc, "statement", "")),
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


def _validate_capacity(value: Optional[float], *, convert_to_hours: bool = False) -> None:
    if value is not None and (
        not math.isfinite(value)
        or (convert_to_hours and not math.isfinite(value * _HOURS_PER_FTE_CAPACITY))
    ):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Capacity must be finite")


def _member_capacity_fields(payload: TeamMemberCreate | TeamMemberUpdate) -> tuple[Optional[int], Optional[float]]:
    _validate_capacity(payload.capacity_fte_month, convert_to_hours=True)
    _validate_capacity(payload.percent_capacity)
    if payload.capacity_fte_month is not None:
        fte = round(max(float(payload.capacity_fte_month), 0.0), 3)
        return _hours_from_fte(fte), fte
    if payload.hours_capacity is not None:
        hours = _checked_hours(payload.hours_capacity)
        return hours, _fte_from_hours(hours)
    return None, None


def _team_capacity_defaults(
    payload: TeamCreate | TeamUpdate,
) -> tuple[Optional[int], Optional[float]]:
    _validate_capacity(payload.default_capacity_fte_month, convert_to_hours=True)
    provided_fields = getattr(payload, "model_fields_set", set())
    if "default_capacity_fte_month" in provided_fields:
        fte = round(max(float(payload.default_capacity_fte_month or 0.0), 0.0), 3)
        return _hours_from_fte(fte), fte
    if "default_capacity_per_week" in provided_fields:
        hours = _checked_hours(payload.default_capacity_per_week or 0)
        return hours, _fte_from_hours(hours)
    return None, None


def _team_with_members(session: Session, team: Team, space_ctx: SpaceContext) -> TeamRead:
    members = (
        _member_query(session, space_ctx)
        .filter(TeamMember.team_id == team.team_id)
        .order_by(TeamMember.created_at.asc())
        .all()
    )
    data = TeamRead.model_validate(team)
    data.members = [TeamMemberRead.model_validate(member) for member in members]
    return data


def _recompute_team_capacity(session: Session, team: Team, space_ctx: SpaceContext) -> None:
    try:
        total = (
            session.query(func.coalesce(func.sum(TeamMember.hours_capacity), 0))
            .filter(TeamMember.team_id == team.team_id)
            .filter(TeamMember.deleted_at.is_(None))
            .filter(TeamMember.space_id == space_ctx.space_id)
            .scalar()
        )
    except OperationalError as exc:
        if session.get_bind().dialect.name == "sqlite" and "integer overflow" in str(exc.orig).lower():
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Team capacity is too large") from exc
        raise
    total_hours = int(total or 0)
    if not -MAX_DB_INTEGER - 1 <= total_hours <= MAX_DB_INTEGER:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Team capacity is too large")
    team.default_capacity_per_week = total_hours
    team.default_capacity_fte_month = _fte_from_hours(team.default_capacity_per_week)
    team.capacity_unit = "fte_month"
    team.updated_at = datetime.now(timezone.utc)
    session.add(team)


def _commit_team_member_capacity_change(
    session: Session,
    locked_team: Team,
    space_ctx: SpaceContext,
    member_to_refresh: Optional[TeamMember] = None,
) -> Optional[TeamMemberRead]:
    try:
        session.flush()
        _recompute_team_capacity(session, locked_team, space_ctx)
        member_read = None
        if member_to_refresh is not None:
            session.refresh(member_to_refresh)
            member_read = TeamMemberRead.model_validate(member_to_refresh)
        session.commit()
    except Exception:
        session.rollback()
        raise
    return member_read


@router.get("/teams", response_model=List[TeamRead])
def list_teams(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[TeamRead]:
    scope_token = make_scope_token("teams", space_ctx.space_id)

    def _load():
        rows = (
            _team_query(session, space_ctx)
            .order_by(Team.created_at.asc())
            .all()
        )
        if not rows:
            return []
        members = (
            _member_query(session, space_ctx)
            .join(Team, Team.team_id == TeamMember.team_id)
            .filter(Team.space_id == space_ctx.space_id)
            .filter(Team.deleted_at.is_(None))
            .order_by(TeamMember.created_at.asc())
            .all()
        )
        members_by_team: dict[str, list[TeamMemberRead]] = {}
        for member in members:
            members_by_team.setdefault(member.team_id, []).append(TeamMemberRead.model_validate(member))
        result = []
        for row in rows:
            data = TeamRead.model_validate(row)
            data.members = members_by_team.get(row.team_id, [])
            result.append(data.model_dump(mode="json"))
        return result

    return cached_call(
        endpoint="teams:list",
        params={},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_TEAMS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/teams", response_model=TeamRead, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> TeamRead:
    existing = (
        session.query(Team)
        .filter(Team.space_id == space_ctx.space_id)
        .filter(Team.name == payload.name)
        .order_by(Team.created_at.asc())
        .first()
    )
    now = datetime.now(timezone.utc)
    if existing and existing.deleted_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Team name already exists",
        )
    if existing and existing.deleted_at is not None:
        existing.deleted_at = None
        existing.description = payload.description
        existing.lead = payload.lead
        existing.updated_at = now
        existing.capacity_unit = payload.capacity_unit or "fte_month"
        default_capacity_per_week, default_capacity_fte_month = _team_capacity_defaults(payload)
        if default_capacity_per_week is not None and default_capacity_fte_month is not None:
            existing.default_capacity_per_week = default_capacity_per_week
            existing.default_capacity_fte_month = default_capacity_fte_month
        session.add(existing)
        session.commit()
        invalidate_space(space_ctx.space_id, ["teams"])
        session.refresh(existing)
        return _team_with_members(session, existing, space_ctx)

    default_capacity_per_week, default_capacity_fte_month = _team_capacity_defaults(payload)
    team = Team(
        space_id=space_ctx.space_id,
        name=payload.name,
        description=payload.description,
        lead=payload.lead,
        default_capacity_per_week=default_capacity_per_week or 0,
        default_capacity_fte_month=default_capacity_fte_month or 0.0,
        capacity_unit=payload.capacity_unit or "fte_month",
        created_at=now,
        updated_at=now,
    )
    try:
        session.add(team)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_team_name_conflict_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team name already exists",
            ) from exc
        raise
    invalidate_space(space_ctx.space_id, ["teams"])
    session.refresh(team)
    return _team_with_members(session, team, space_ctx)


@router.get("/teams/{team_id}", response_model=TeamRead)
def get_team(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> TeamRead:
    scope_token = make_scope_token("teams", space_ctx.space_id)

    def _load():
        team = _active_team(session, team_id, space_ctx)
        return _team_with_members(session, team, space_ctx).model_dump(mode="json")

    return cached_call(
        endpoint="teams:detail",
        params={"team_id": team_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_TEAMS_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.patch("/teams/{team_id}", response_model=TeamRead)
def update_team(
    team_id: str,
    payload: TeamUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> TeamRead:
    team = _lock_active_team(session, team_id, space_ctx)
    _validate_capacity(payload.default_capacity_fte_month, convert_to_hours=True)
    old_name = team.name
    affected_user_ids: set[str] = set()
    for field in ["name", "description", "lead"]:
        val = getattr(payload, field)
        if val is not None:
            setattr(team, field, val)
    if payload.default_capacity_fte_month is not None:
        team.default_capacity_fte_month = round(max(float(payload.default_capacity_fte_month), 0.0), 3)
        team.default_capacity_per_week = _hours_from_fte(team.default_capacity_fte_month)
    elif payload.default_capacity_per_week is not None:
        team.default_capacity_per_week = _checked_hours(payload.default_capacity_per_week)
        team.default_capacity_fte_month = _fte_from_hours(team.default_capacity_per_week)
    if payload.capacity_unit is not None:
        team.capacity_unit = payload.capacity_unit
    if team.name != old_name:
        for user in _space_user_membership_query(session, space_ctx).filter(User.team_tag == old_name).all():
            user.team_tag = team.name
            user.updated_at = datetime.now(timezone.utc)
            session.add(user)
            affected_user_ids.add(user.user_id)
    team.updated_at = datetime.now(timezone.utc)
    try:
        session.add(team)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_team_name_conflict_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team name already exists",
            ) from exc
        raise
    invalidate_space(space_ctx.space_id, ["teams"])
    _invalidate_user_caches_for_user_memberships(session, affected_user_ids)
    session.refresh(team)
    return _team_with_members(session, team, space_ctx)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> None:
    team = _lock_active_team(session, team_id, space_ctx)
    now = datetime.now(timezone.utc)
    old_name = team.name
    affected_user_ids: set[str] = set()
    team.deleted_at = now
    _member_query(session, space_ctx).filter(TeamMember.team_id == team_id).update({"deleted_at": now})
    for user in _space_user_membership_query(session, space_ctx).filter(User.team_tag == old_name).all():
        user.team_tag = None
        user.updated_at = now
        session.add(user)
        affected_user_ids.add(user.user_id)
    session.add(team)
    session.commit()
    invalidate_space(space_ctx.space_id, ["teams"])
    _invalidate_user_caches_for_user_memberships(session, affected_user_ids)
    return None


@router.get("/teams/{team_id}/members", response_model=List[TeamMemberRead])
def list_team_members(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> List[TeamMemberRead]:
    scope_token = make_scope_token("teams", space_ctx.space_id)

    def _load():
        _active_team(session, team_id, space_ctx)
        members = (
            _member_query(session, space_ctx)
            .filter(TeamMember.team_id == team_id)
            .order_by(TeamMember.created_at.asc())
            .all()
        )
        return [TeamMemberRead.model_validate(member).model_dump(mode="json") for member in members]

    return cached_call(
        endpoint="teams:members",
        params={"team_id": team_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_TEAMS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/teams/{team_id}/members", response_model=TeamMemberRead, status_code=status.HTTP_201_CREATED)
def create_team_member(
    team_id: str,
    payload: TeamMemberCreate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> TeamMemberRead:
    team = _lock_active_team(session, team_id, space_ctx)
    hours_capacity, capacity_fte_month = _member_capacity_fields(payload)
    member = TeamMember(
        space_id=space_ctx.space_id,
        team_id=team_id,
        member_name=payload.member_name,
        role=payload.role or "member",
        capacity_override=payload.capacity_override,
        capacity_unit=payload.capacity_unit or "fte_month",
        hours_capacity=hours_capacity,
        capacity_fte_month=capacity_fte_month,
        points_capacity=payload.points_capacity,
        percent_capacity=payload.percent_capacity,
    )
    session.add(member)
    member_read = _commit_team_member_capacity_change(
        session,
        team,
        space_ctx,
        member_to_refresh=member,
    )
    invalidate_space(space_ctx.space_id, ["teams"])
    assert member_read is not None
    return member_read


@router.patch("/teams/{team_id}/members/{member_id}", response_model=TeamMemberRead)
def update_team_member(
    team_id: str,
    member_id: str,
    payload: TeamMemberUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> TeamMemberRead:
    team = _lock_active_team(session, team_id, space_ctx)
    member = _active_member(session, member_id, team_id, space_ctx)
    for field in ["member_name", "role", "capacity_override", "capacity_unit"]:
        val = getattr(payload, field)
        if val is not None:
            setattr(member, field, val)
    hours_capacity, capacity_fte_month = _member_capacity_fields(payload)
    if hours_capacity is not None:
        member.hours_capacity = hours_capacity
    if capacity_fte_month is not None:
        member.capacity_fte_month = capacity_fte_month
    if hours_capacity is not None or capacity_fte_month is not None:
        member.capacity_unit = payload.capacity_unit or member.capacity_unit or "fte_month"
    for field in ["points_capacity", "percent_capacity"]:
        if getattr(payload, field) is not None:
            setattr(member, field, getattr(payload, field))
    member.updated_at = datetime.now(timezone.utc)
    session.add(member)
    member_read = _commit_team_member_capacity_change(
        session,
        team,
        space_ctx,
        member_to_refresh=member,
    )
    invalidate_space(space_ctx.space_id, ["teams"])
    assert member_read is not None
    return member_read


@router.delete("/teams/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(
    team_id: str,
    member_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> None:
    team = _lock_active_team(session, team_id, space_ctx)
    member = _active_member(session, member_id, team_id, space_ctx)
    member.deleted_at = datetime.now(timezone.utc)
    _commit_team_member_capacity_change(session, team, space_ctx)
    invalidate_space(space_ctx.space_id, ["teams"])
    return None


