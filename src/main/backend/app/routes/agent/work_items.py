from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...deps import current_agent_space, get_db, require_agent_space_role
from ...schemas.agent import AgentProjectRead, AgentSolutionRead, AgentTaskRead
from ...services.agent_work_items import (
    get_agent_project,
    get_agent_solution,
    get_agent_task,
)
from ...services.spaces import SpaceContext

router = APIRouter()


@router.get(
    "/projects/{project_id}",
    response_model=AgentProjectRead,
    operation_id="agent_get_project",
    summary="Get one complete scoped project",
)
def get_project(
    project_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentProjectRead:
    return get_agent_project(session, project_id, space_ctx)


@router.get(
    "/solutions/{solution_id}",
    response_model=AgentSolutionRead,
    operation_id="agent_get_solution",
    summary="Get one complete scoped solution",
)
def get_solution(
    solution_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentSolutionRead:
    return get_agent_solution(session, solution_id, space_ctx)


@router.get(
    "/tasks/{task_id}",
    response_model=AgentTaskRead,
    operation_id="agent_get_task",
    summary="Get one complete scoped task",
)
def get_task(
    task_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentTaskRead:
    return get_agent_task(session, task_id, space_ctx)
