from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import current_agent_space, get_db, require_agent_space_role
from ...schemas.agent import (
    AgentPeopleListRead,
    AgentTeamListRead,
    AgentTeamMemberListRead,
)
from ...services.agent_people import (
    list_agent_people,
    list_agent_team_members,
    list_agent_teams,
)
from ...services.spaces import SpaceContext

router = APIRouter()


@router.get(
    "/people",
    response_model=AgentPeopleListRead,
    operation_id="agent_list_people",
    summary="List assignable people in the scoped space",
)
def get_people(
    q: str | None = Query(None, min_length=2, max_length=100),
    soeid: str | None = None,
    role: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentPeopleListRead:
    return list_agent_people(
        session, space_ctx, q=q, soeid=soeid, role=role, cursor=cursor, limit=limit
    )


@router.get(
    "/teams",
    response_model=AgentTeamListRead,
    operation_id="agent_list_teams",
    summary="List scoped teams and capacity",
)
def get_teams(
    q: str | None = Query(None, min_length=2, max_length=100),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentTeamListRead:
    return list_agent_teams(session, space_ctx, q=q, cursor=cursor, limit=limit)


@router.get(
    "/teams/{team_id}/members",
    response_model=AgentTeamMemberListRead,
    operation_id="agent_list_team_members",
    summary="List scoped team membership and capacity",
)
def get_team_members(
    team_id: str,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentTeamMemberListRead:
    return list_agent_team_members(
        session, space_ctx, team_id, cursor=cursor, limit=limit
    )
