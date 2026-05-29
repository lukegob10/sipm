from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import current_agent_space, get_db, require_agent_space_role
from ...schemas.agent import AgentWorkGraphRead
from ...services.agent_work_graph import build_work_graph
from ...services.spaces import SpaceContext

router = APIRouter()


@router.get(
    "/work-graph",
    response_model=AgentWorkGraphRead,
    operation_id="agent_get_work_graph",
    summary="Get scoped project solution subcomponent graph",
)
def get_agent_work_graph(
    project_id: str | None = None,
    solution_id: str | None = None,
    status: str | None = None,
    owner_user_soeid: str | None = None,
    assignee_user_soeid: str | None = None,
    updated_since: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
):
    return build_work_graph(
        session,
        space_ctx,
        project_id=project_id,
        solution_id=solution_id,
        status=status,
        owner_user_soeid=owner_user_soeid,
        assignee_user_soeid=assignee_user_soeid,
        updated_since=updated_since,
        limit=limit,
    )
