from __future__ import annotations

from fastapi import APIRouter, Depends

from ...auth.auth import DELEGATED_TOKEN_EXPIRE_MINUTES
from ...deps import require_agent_service_account
from ...paths import APP_CONTEXT_PATH
from ...schemas.agent import AgentManifestRead
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
):
    return AgentManifestRead(
        name="SIPM Agent API",
        version="1.2",
        context_path=APP_CONTEXT_PATH or "",
        requires_space_id=True,
        space_discovery_requires_space_id=False,
        space_discovery_path="/api/agent/spaces",
        auth={
            "type": "bearer",
            "service_account_required": True,
            "delegated_session_path": "/api/agent/delegated-session",
            "delegated_token_ttl_minutes": DELEGATED_TOKEN_EXPIRE_MINUTES,
        },
        capabilities=[
            "read_programs",
            "read_spaces",
            "read_work_graph",
            "read_paginated_work_graph",
            "read_work_item_details",
            "search_work_items",
            "read_own_change_requests",
            "cancel_own_change_request",
            "archive_work_items",
            "human_delegated_review",
            "read_audit_feed",
            "read_reference_data",
            "read_agent_openapi",
            "read_people_and_teams",
            "validate_patch",
            "submit_change_request",
        ],
        writable_entities=sorted(VALID_ENTITIES),
        writable_actions=sorted(VALID_OPS),
        writes_require_change_request=True,
        human_review_required=True,
        service_account_can_approve=False,
        human_delegated_review=True,
        max_patch_operations=25,
    )
