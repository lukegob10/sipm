from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ...deps import (
    current_agent_space,
    get_db,
    require_agent_service_account,
    require_agent_space_role,
)
from ...models import User
from ...security import security_http_exception
from ...schemas.agent import AgentPatchRequest, AgentPatchResponse
from ...services.agent_patch_plan import validate_patch_plan
from ...services.spaces import SpaceContext

router = APIRouter(prefix="/patches")


@router.post(
    "/validate",
    response_model=AgentPatchResponse,
    operation_id="agent_validate_patch",
    summary="Validate controlled agent patch",
)
def validate_agent_patch(
    payload: AgentPatchRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
):
    return validate_patch_plan(session, space_ctx, payload)


@router.post(
    "/apply",
    response_model=AgentPatchResponse,
    operation_id="agent_apply_patch",
    summary="Apply controlled agent patch",
)
def apply_agent_patch(
    payload: AgentPatchRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_service_account),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
):
    raise security_http_exception(
        status_code=status.HTTP_403_FORBIDDEN,
        code="AGENT_APPROVAL_REQUIRED",
        message="Agent patch application requires human approval",
    )
