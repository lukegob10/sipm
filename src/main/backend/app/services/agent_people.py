from __future__ import annotations

from fastapi import status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..models import SpaceMembership, Team, TeamMember, User
from ..schemas.agent import (
    AgentPeopleListRead,
    AgentPersonRead,
    AgentTeamListRead,
    AgentTeamMemberListRead,
    AgentTeamMemberRead,
    AgentTeamRead,
)
from ..security import security_http_exception
from ..utils import normalize_str
from .agent_pagination import decode_position_cursor, encode_position_cursor
from .spaces import SpaceContext

PEOPLE_CURSOR_SCOPE = "agent_people_v1"
TEAMS_CURSOR_SCOPE = "agent_teams_v1"
TEAM_MEMBERS_CURSOR_SCOPE = "agent_team_members_v1"


def list_agent_people(
    session: Session,
    space_ctx: SpaceContext,
    *,
    q: str | None = None,
    soeid: str | None = None,
    role: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> AgentPeopleListRead:
    normalized_q = normalize_str(q).lower() or None
    normalized_soeid = normalize_str(soeid).lower() or None
    normalized_role = normalize_str(role).lower() or None
    filters = {
        "space_id": space_ctx.space_id,
        "q": normalized_q,
        "soeid": normalized_soeid,
        "role": normalized_role,
    }
    query = (
        session.query(User, SpaceMembership.role)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(
            SpaceMembership.space_id == space_ctx.space_id,
            SpaceMembership.status == "active",
            SpaceMembership.deleted_at.is_(None),
            User.is_active,
        )
    )
    if normalized_soeid:
        query = query.filter(func.lower(User.soeid) == normalized_soeid)
    if normalized_role:
        query = query.filter(func.lower(SpaceMembership.role) == normalized_role)
    if normalized_q:
        pattern = f"%{normalized_q}%"
        query = query.filter(
            or_(
                func.lower(User.display_name).like(pattern),
                func.lower(User.soeid).like(pattern),
            )
        )
    if cursor:
        position = decode_position_cursor(
            cursor, scope=PEOPLE_CURSOR_SCOPE, filters=filters
        )
        name, user_id = str(position.get("name", "")), str(position.get("user_id", ""))
        if not name or not user_id:
            raise security_http_exception(
                status_code=400,
                code="INVALID_CURSOR",
                message="Cursor is invalid for this request",
            )
        query = query.filter(
            or_(
                User.display_name > name,
                and_(User.display_name == name, User.user_id > user_id),
            )
        )
    rows = (
        query.order_by(User.display_name.asc(), User.user_id.asc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        next_cursor = encode_position_cursor(
            scope=PEOPLE_CURSOR_SCOPE,
            filters=filters,
            position={"name": rows[-1][0].display_name, "user_id": rows[-1][0].user_id},
        )
    return AgentPeopleListRead(
        space_id=space_ctx.space_id,
        records=[
            AgentPersonRead(
                user_id=user.user_id,
                soeid=user.soeid,
                display_name=user.display_name,
                membership_role=membership_role,
                team_tag=user.team_tag,
                capacity_hours=user.capacity_hours,
                capacity_fte_month=user.capacity_fte_month,
                is_service_account=user.is_service_account,
                updated_at=user.updated_at,
            )
            for user, membership_role in rows
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def _team_base_query(session: Session, space_ctx: SpaceContext):
    return session.query(Team).filter(
        Team.space_id == space_ctx.space_id, Team.deleted_at.is_(None)
    )


def list_agent_teams(
    session: Session,
    space_ctx: SpaceContext,
    *,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> AgentTeamListRead:
    normalized_q = normalize_str(q).lower() or None
    filters = {"space_id": space_ctx.space_id, "q": normalized_q}
    query = _team_base_query(session, space_ctx)
    if normalized_q:
        query = query.filter(func.lower(Team.name).like(f"%{normalized_q}%"))
    if cursor:
        position = decode_position_cursor(
            cursor, scope=TEAMS_CURSOR_SCOPE, filters=filters
        )
        name, team_id = str(position.get("name", "")), str(position.get("team_id", ""))
        if not name or not team_id:
            raise security_http_exception(
                status_code=400,
                code="INVALID_CURSOR",
                message="Cursor is invalid for this request",
            )
        query = query.filter(
            or_(Team.name > name, and_(Team.name == name, Team.team_id > team_id))
        )
    rows = query.order_by(Team.name.asc(), Team.team_id.asc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    counts = dict(
        session.query(TeamMember.team_id, func.count(TeamMember.team_member_id))
        .filter(
            TeamMember.space_id == space_ctx.space_id,
            TeamMember.deleted_at.is_(None),
            TeamMember.team_id.in_([row.team_id for row in rows] or ["-"]),
        )
        .group_by(TeamMember.team_id)
        .all()
    )
    next_cursor = (
        encode_position_cursor(
            scope=TEAMS_CURSOR_SCOPE,
            filters=filters,
            position={"name": rows[-1].name, "team_id": rows[-1].team_id},
        )
        if has_more and rows
        else None
    )
    return AgentTeamListRead(
        space_id=space_ctx.space_id,
        records=[
            AgentTeamRead.model_validate(
                {
                    **{
                        field: getattr(row, field)
                        for field in AgentTeamRead.model_fields
                        if field != "member_count"
                    },
                    "member_count": counts.get(row.team_id, 0),
                }
            )
            for row in rows
        ],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def list_agent_team_members(
    session: Session,
    space_ctx: SpaceContext,
    team_id: str,
    *,
    cursor: str | None = None,
    limit: int = 50,
) -> AgentTeamMemberListRead:
    if (
        _team_base_query(session, space_ctx).filter(Team.team_id == team_id).first()
        is None
    ):
        raise security_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            code="TEAM_NOT_FOUND",
            message="Team not found",
        )
    filters = {"space_id": space_ctx.space_id, "team_id": team_id}
    query = session.query(TeamMember).filter(
        TeamMember.space_id == space_ctx.space_id,
        TeamMember.team_id == team_id,
        TeamMember.deleted_at.is_(None),
    )
    if cursor:
        position = decode_position_cursor(
            cursor, scope=TEAM_MEMBERS_CURSOR_SCOPE, filters=filters
        )
        name, member_id = (
            str(position.get("name", "")),
            str(position.get("team_member_id", "")),
        )
        if not name or not member_id:
            raise security_http_exception(
                status_code=400,
                code="INVALID_CURSOR",
                message="Cursor is invalid for this request",
            )
        query = query.filter(
            or_(
                TeamMember.member_name > name,
                and_(
                    TeamMember.member_name == name,
                    TeamMember.team_member_id > member_id,
                ),
            )
        )
    rows = (
        query.order_by(TeamMember.member_name.asc(), TeamMember.team_member_id.asc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = (
        encode_position_cursor(
            scope=TEAM_MEMBERS_CURSOR_SCOPE,
            filters=filters,
            position={
                "name": rows[-1].member_name,
                "team_member_id": rows[-1].team_member_id,
            },
        )
        if has_more and rows
        else None
    )
    return AgentTeamMemberListRead(
        space_id=space_ctx.space_id,
        team_id=team_id,
        records=[AgentTeamMemberRead.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
