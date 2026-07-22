from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import current_agent_space, get_db, require_agent_space_role
from ...schemas.agent import AgentAssignedWorkListRead
from ...services.agent_assigned_work import list_agent_assigned_work
from ...services.spaces import SpaceContext


router = APIRouter()


@router.get(
    "/assigned-work",
    response_model=AgentAssignedWorkListRead,
    operation_id="agent_list_assigned_work",
    summary="List active shared tasks assigned to one person",
)
def list_assigned_work(
    assignee_user_soeid: str = Query(..., min_length=1, max_length=100),
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentAssignedWorkListRead:
    return list_agent_assigned_work(
        session,
        space_ctx,
        assignee_user_soeid=assignee_user_soeid,
        cursor=cursor,
        limit=limit,
    )
