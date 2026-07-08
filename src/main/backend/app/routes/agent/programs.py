from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...deps import current_agent_space, get_db, require_agent_space_role
from ...models import Program
from ...schemas.agent import AgentProgramNode
from ...services.programs import program_query
from ...services.spaces import SpaceContext

router = APIRouter(prefix="/programs")


def _program_node(program: Program) -> AgentProgramNode:
    return AgentProgramNode(
        program_id=program.program_id,
        program_name=program.program_name,
        description=program.description,
        updated_at=program.updated_at,
    )


@router.get(
    "",
    response_model=list[AgentProgramNode],
    operation_id="agent_list_programs",
    summary="List scoped programs",
)
def list_agent_programs(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> list[AgentProgramNode]:
    rows = program_query(session, space_ctx).order_by(Program.program_name.asc()).all()
    return [_program_node(row) for row in rows]


@router.get(
    "/{program_id}",
    response_model=AgentProgramNode,
    operation_id="agent_get_program",
    summary="Get scoped program",
)
def get_agent_program(
    program_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentProgramNode:
    program = (
        program_query(session, space_ctx)
        .filter(Program.program_id == program_id)
        .first()
    )
    if not program:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Program not found",
        )
    return _program_node(program)
