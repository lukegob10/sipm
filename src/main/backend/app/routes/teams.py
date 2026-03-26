from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..models import SpaceMembership, Team, TeamMember, User
from ..schemas import TeamCreate, TeamRead, TeamUpdate, TeamMemberCreate, TeamMemberRead, TeamMemberUpdate
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token

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


def _active_team(session: Session, team_id: str, space_ctx: SpaceContext) -> Team:
    team = (
        _team_query(session, space_ctx)
        .filter(Team.team_id == team_id)
        .first()
    )
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


def _fte_from_hours(hours: Optional[int]) -> float:
    return round(max(float(hours or 0), 0.0) / _HOURS_PER_FTE_CAPACITY, 3)


def _hours_from_fte(fte_month: Optional[float]) -> int:
    return max(int(round(max(float(fte_month or 0.0), 0.0) * _HOURS_PER_FTE_CAPACITY)), 0)


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


def _member_capacity_fields(payload: TeamMemberCreate | TeamMemberUpdate) -> tuple[Optional[int], Optional[float]]:
    if payload.capacity_fte_month is not None:
        fte = round(max(float(payload.capacity_fte_month), 0.0), 3)
        return _hours_from_fte(fte), fte
    if payload.hours_capacity is not None:
        hours = max(int(payload.hours_capacity), 0)
        return hours, _fte_from_hours(hours)
    return None, None


def _team_capacity_defaults(
    payload: TeamCreate | TeamUpdate,
) -> tuple[Optional[int], Optional[float]]:
    provided_fields = getattr(payload, "model_fields_set", set())
    if "default_capacity_fte_month" in provided_fields:
        fte = round(max(float(payload.default_capacity_fte_month or 0.0), 0.0), 3)
        return _hours_from_fte(fte), fte
    if "default_capacity_per_week" in provided_fields:
        hours = max(int(payload.default_capacity_per_week or 0), 0)
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


def _recompute_team_capacity(session: Session, team_id: str, space_ctx: SpaceContext) -> None:
    total = (
        session.query(func.coalesce(func.sum(TeamMember.hours_capacity), 0))
        .filter(TeamMember.team_id == team_id)
        .filter(TeamMember.deleted_at.is_(None))
        .filter(TeamMember.space_id == space_ctx.space_id)
        .scalar()
    )
    team = _team_query(session, space_ctx).filter(Team.team_id == team_id).first()
    if not team:
        return
    team.default_capacity_per_week = int(total or 0)
    team.default_capacity_fte_month = _fte_from_hours(team.default_capacity_per_week)
    team.capacity_unit = "fte_month"
    team.updated_at = datetime.now(timezone.utc)
    session.add(team)
    session.commit()


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
        return [
            _team_with_members(session, row, space_ctx).model_dump(mode="json")
            for row in rows
        ]

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
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
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
        session.refresh(existing)
        invalidate_space(space_ctx.space_id, ["teams"])
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
        session.refresh(team)
    except IntegrityError as exc:
        session.rollback()
        if _is_team_name_conflict_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Team name already exists",
            ) from exc
        raise
    invalidate_space(space_ctx.space_id, ["teams"])
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
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> TeamRead:
    team = _active_team(session, team_id, space_ctx)
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
        team.default_capacity_per_week = max(int(payload.default_capacity_per_week), 0)
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
        session.refresh(team)
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
    return _team_with_members(session, team, space_ctx)


@router.delete("/teams/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team(
    team_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    team = _active_team(session, team_id, space_ctx)
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
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> TeamMemberRead:
    _active_team(session, team_id, space_ctx)
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
    session.commit()
    session.refresh(member)
    _recompute_team_capacity(session, team_id, space_ctx)
    invalidate_space(space_ctx.space_id, ["teams"])
    return TeamMemberRead.model_validate(member)


@router.patch("/teams/{team_id}/members/{member_id}", response_model=TeamMemberRead)
def update_team_member(
    team_id: str,
    member_id: str,
    payload: TeamMemberUpdate,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> TeamMemberRead:
    _active_team(session, team_id, space_ctx)
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
    session.commit()
    session.refresh(member)
    _recompute_team_capacity(session, team_id, space_ctx)
    invalidate_space(space_ctx.space_id, ["teams"])
    return TeamMemberRead.model_validate(member)


@router.delete("/teams/{team_id}/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_team_member(
    team_id: str,
    member_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
) -> None:
    _active_team(session, team_id, space_ctx)
    member = _active_member(session, member_id, team_id, space_ctx)
    member.deleted_at = datetime.now(timezone.utc)
    session.add(member)
    session.commit()
    _recompute_team_capacity(session, team_id, space_ctx)
    invalidate_space(space_ctx.space_id, ["teams"])
    return None


