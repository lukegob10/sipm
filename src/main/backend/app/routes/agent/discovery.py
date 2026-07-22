from __future__ import annotations

from copy import deepcopy
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from ...auth.auth import DELEGATED_TOKEN_EXPIRE_MINUTES, create_token
from ...deps import (
    current_agent_space,
    get_db,
    require_agent_service_account,
    require_agent_space_role,
    require_interactive_user,
)
from ...models import Phase, User
from ...paths import API_PREFIX
from ...schemas.agent import (
    AgentAuditFeedRead,
    AgentDelegatedTokenRead,
    AgentReferenceDataRead,
)
from ...services.agent_audit import list_agent_audit_feed
from ...services.agent_patch_plan import (
    CREATE_FIELDS,
    UPDATE_FIELDS,
    VALID_ENTITIES,
    VALID_OPS,
)
from ...services.spaces import SpaceContext
from ...utils.enums import (
    ConfidenceLevel,
    ProjectStatus,
    RagStatus,
    SolutionStatus,
    TaskStatus,
)

router = APIRouter()
REFERENCE_VERSION = "1.1"


@router.post(
    "/delegated-session",
    response_model=AgentDelegatedTokenRead,
    operation_id="agent_create_delegated_session",
    summary="Issue a short-lived delegated-review token from a human session",
)
def create_delegated_session(
    request: Request,
    current_user: User = Depends(require_interactive_user),
) -> AgentDelegatedTokenRead:
    auth_session = getattr(request.state, "auth_session", None)
    if auth_session is None:
        raise RuntimeError("Authenticated session context is missing")
    token = create_token(
        current_user.user_id,
        current_user.role,
        "delegated",
        session_id=auth_session.session_id,
    )
    return AgentDelegatedTokenRead(
        access_token=token,
        expires_in_seconds=DELEGATED_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/audit-feed",
    response_model=AgentAuditFeedRead,
    operation_id="agent_get_audit_feed",
    summary="Traverse scoped audit events",
)
def get_audit_feed(
    since: datetime | None = None,
    until: datetime | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_agent_space),
    _authz: SpaceContext = Depends(require_agent_space_role("member")),
) -> AgentAuditFeedRead:
    return list_agent_audit_feed(
        session,
        space_ctx,
        since=since,
        until=until,
        entity_type=entity_type,
        entity_id=entity_id,
        user_id=user_id,
        request_id=request_id,
        cursor=cursor,
        limit=limit,
    )


def _values(enum_type) -> list[str]:
    return [item.value for item in enum_type]


@router.get(
    "/reference-data",
    response_model=AgentReferenceDataRead,
    operation_id="agent_get_reference_data",
    summary="Get machine-readable Agent API contracts",
)
def get_reference_data(
    response: Response,
    session: Session = Depends(get_db),
    _user=Depends(require_agent_service_account),
) -> AgentReferenceDataRead:
    response.headers["ETag"] = f'"agent-reference-{REFERENCE_VERSION}"'
    statuses = {
        "project": _values(ProjectStatus),
        "solution": _values(SolutionStatus),
        "task": _values(TaskStatus),
    }
    return AgentReferenceDataRead(
        version=REFERENCE_VERSION,
        entity_types=sorted(VALID_ENTITIES),
        operations=sorted(VALID_OPS),
        fields={
            entity: {
                "create": sorted(CREATE_FIELDS[entity]),
                "update": sorted(UPDATE_FIELDS[entity]),
                "archive": [],
            }
            for entity in sorted(VALID_ENTITIES)
        },
        statuses=statuses,
        status_transitions={
            entity: {value: list(values) for value in values}
            for entity, values in statuses.items()
        },
        rag_statuses=_values(RagStatus),
        confidence_levels=_values(ConfidenceLevel),
        phases=[
            {
                "phase_id": row.phase_id,
                "phase_group": row.phase_group,
                "phase_name": row.phase_name,
                "sequence": row.sequence,
            }
            for row in session.query(Phase)
            .order_by(Phase.sequence.asc(), Phase.phase_id.asc())
            .all()
        ],
        limits={
            "patch_operations": 25,
            "page_default": 50,
            "page_max": 200,
            "audit_page_max": 500,
        },
        filters={
            "spaces": ["space_id", "slug", "name", "cursor", "limit"],
            "work_items": [
                "entity_type",
                "entity_id",
                "parent_id",
                "exact_name",
                "q",
                "status",
                "principal_soeid",
                "due_from",
                "due_to",
                "updated_since",
                "lifecycle",
                "cursor",
                "limit",
            ],
            "assigned_work": [
                "assignee_user_soeid",
                "cursor",
                "limit",
            ],
            "work_graph": [
                "project_id",
                "solution_id",
                "task_id",
                "status",
                "owner_user_soeid",
                "assignee_user_soeid",
                "updated_since",
                "projection",
                "cursor",
                "limit",
            ],
            "audit_feed": [
                "since",
                "until",
                "entity_type",
                "entity_id",
                "user_id",
                "request_id",
                "cursor",
                "limit",
            ],
            "people": ["q", "soeid", "role", "cursor", "limit"],
            "teams": ["q", "cursor", "limit"],
            "team_members": ["cursor", "limit"],
        },
    )


@router.get(
    "/openapi.json",
    operation_id="agent_get_openapi",
    summary="Get the Agent-only OpenAPI contract",
)
def get_agent_openapi(
    request: Request,
    _user=Depends(require_agent_service_account),
) -> dict:
    source = request.app.openapi()
    agent_prefix = f"{API_PREFIX}/agent"
    document = {
        "openapi": source.get("openapi", "3.1.0"),
        "info": {"title": "SIPM Agent API", "version": "1.0"},
        "paths": {
            path: deepcopy(value)
            for path, value in source.get("paths", {}).items()
            if path == agent_prefix or path.startswith(f"{agent_prefix}/")
        },
        "components": deepcopy(source.get("components", {})),
    }
    schemes = document.setdefault("components", {}).setdefault("securitySchemes", {})
    schemes["AgentBearer"] = {"type": "http", "scheme": "bearer"}
    schemes["HumanSessionCookie"] = {
        "type": "apiKey",
        "in": "cookie",
        "name": "access_token",
    }
    for path, methods in document["paths"].items():
        for method, operation in methods.items():
            if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                continue
            operation["x-agent-safe"] = True
            operation["x-approval-gated"] = (
                "change-requests" in path and method.lower() == "post"
            )
            operation.setdefault("security", [{"AgentBearer": []}])
            if path.endswith("/delegated-session"):
                operation["security"] = [{"HumanSessionCookie": []}]
                continue
            if (
                path.endswith("/manifest")
                or "/spaces" in path
                or path.endswith("/reference-data")
                or path.endswith("/openapi.json")
            ):
                continue
            parameters = operation.setdefault("parameters", [])
            if not any(item.get("name") == "X-Space-Id" for item in parameters):
                parameters.append(
                    {
                        "name": "X-Space-Id",
                        "in": "header",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "Explicit accessible space scope",
                    }
                )
    return document
