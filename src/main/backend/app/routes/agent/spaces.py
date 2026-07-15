from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import get_db, require_agent_service_account
from ...models import User
from ...schemas.agent import AgentSpaceListRead, AgentSpaceRead
from ...services.agent_spaces import get_agent_space, list_agent_spaces


router = APIRouter(prefix="/spaces")


@router.get(
    "",
    response_model=AgentSpaceListRead,
    operation_id="agent_list_spaces",
    summary="List accessible spaces",
)
def list_spaces(
    space_id: str | None = None,
    slug: str | None = None,
    name: str | None = None,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_service_account),
) -> AgentSpaceListRead:
    return list_agent_spaces(
        session,
        current_user,
        space_id=space_id,
        slug=slug,
        name=name,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/{space_id}",
    response_model=AgentSpaceRead,
    operation_id="agent_get_space",
    summary="Get an accessible space",
)
def get_space(
    space_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_service_account),
) -> AgentSpaceRead:
    return get_agent_space(session, current_user, space_id)
