from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import current_agent_space, get_db, require_agent_space_role
from ...schemas.agent import AgentWorkItemListRead
from ...services.agent_work_search import search_agent_work_items
from ...services.spaces import SpaceContext

router = APIRouter()


@router.get(
    "/work-items",
    response_model=AgentWorkItemListRead,
    operation_id="agent_search_work_items",
    summary="Search one type of work item",
)
def search_work_items(
    entity_type: str,
    entity_id: str | None = None,
    parent_id: str | None = None,
    exact_name: str | None = None,
    q: str | None = Query(None, min_length=2, max_length=100),
    status: str | None = None,
    principal_soeid: str | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    updated_since: datetime | None = None,
    lifecycle: str = "active",
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentWorkItemListRead:
    return search_agent_work_items(
        session,
        space_ctx,
        entity_type=entity_type,
        entity_id=entity_id,
        parent_id=parent_id,
        exact_name=exact_name,
        query_text=q,
        item_status=status,
        principal_soeid=principal_soeid,
        due_from=due_from,
        due_to=due_to,
        updated_since=updated_since,
        lifecycle=lifecycle,
        cursor=cursor,
        limit=limit,
    )
