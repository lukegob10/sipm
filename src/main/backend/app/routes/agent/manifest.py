from __future__ import annotations

from fastapi import APIRouter, Depends

from ...deps import current_agent_space, require_agent_service_account
from ...paths import APP_CONTEXT_PATH
from ...schemas.agent import AgentManifestRead
from ...services.spaces import SpaceContext
from ...services.agent_patch_plan import VALID_ENTITIES, VALID_OPS

router = APIRouter()


@router.get(
    "/manifest",
    response_model=AgentManifestRead,
    operation_id="agent_get_manifest",
    summary="Get Agent API manifest",
)
def get_agent_manifest(
    _user=Depends(require_agent_service_account),
    _space_ctx: SpaceContext = Depends(current_agent_space),
):
    return AgentManifestRead(
        name="SIPM Agent API",
        version="0.1",
        context_path=APP_CONTEXT_PATH or "",
        requires_space_id=True,
        auth={"type": "bearer", "service_account_required": True},
        capabilities=["read_work_graph", "validate_patch", "apply_patch"],
        writable_entities=sorted(VALID_ENTITIES),
        writable_actions=sorted(VALID_OPS),
        max_patch_operations=25,
    )
