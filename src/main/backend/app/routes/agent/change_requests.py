from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ...deps import (
    current_agent_space,
    current_space as current_space_dep,
    get_db,
    require_agent_service_account,
    require_interactive_user,
    require_space_role,
)
from ...models import User
from ...schemas.agent import (
    AgentChangeRequestBulkReview,
    AgentChangeRequestBulkReviewResult,
    AgentChangeRequestListRead,
    AgentChangeRequestRead,
    AgentChangeRequestReview,
    AgentPatchRequest,
)
from ...services.agent_change_requests import (
    approve_change_request,
    approve_selected_change_requests,
    create_change_request,
    get_change_request,
    list_change_requests,
    reject_change_request,
    reject_selected_change_requests,
)
from ...services.spaces import SpaceContext

router = APIRouter(prefix="/change-requests")


@router.post(
    "",
    response_model=AgentChangeRequestRead,
    status_code=201,
    operation_id="agent_create_change_request",
    summary="Create pending agent change request",
)
def submit_agent_change_request(
    payload: AgentPatchRequest,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_service_account),
    space_ctx: SpaceContext = Depends(current_agent_space),
):
    return create_change_request(session, space_ctx, current_user, payload)


@router.get(
    "",
    response_model=AgentChangeRequestListRead,
    operation_id="agent_list_change_requests",
    summary="List agent change requests",
)
def list_agent_change_requests(
    status: str = "pending",
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_db),
    _current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return list_change_requests(
        session,
        space_ctx,
        status_filter=status,
        limit=limit,
    )


@router.get(
    "/{change_request_id}",
    response_model=AgentChangeRequestRead,
    operation_id="agent_get_change_request",
    summary="Get agent change request",
)
def get_agent_change_request(
    change_request_id: str,
    session: Session = Depends(get_db),
    _current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return get_change_request(session, space_ctx, change_request_id)


@router.post(
    "/{change_request_id}/approve",
    response_model=AgentChangeRequestRead,
    operation_id="agent_approve_change_request",
    summary="Approve and apply agent change request",
)
def approve_agent_change_request(
    change_request_id: str,
    payload: AgentChangeRequestReview | None = None,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return approve_change_request(
        session,
        space_ctx,
        current_user,
        change_request_id,
        review_note=payload.review_note if payload else None,
    )


@router.post(
    "/{change_request_id}/reject",
    response_model=AgentChangeRequestRead,
    operation_id="agent_reject_change_request",
    summary="Reject agent change request",
)
def reject_agent_change_request(
    change_request_id: str,
    payload: AgentChangeRequestReview | None = None,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return reject_change_request(
        session,
        space_ctx,
        current_user,
        change_request_id,
        review_note=payload.review_note if payload else None,
    )


@router.post(
    "/actions/approve-selected",
    response_model=AgentChangeRequestBulkReviewResult,
    operation_id="agent_approve_selected_change_requests",
    summary="Approve selected agent change requests",
)
def approve_selected_agent_change_requests(
    payload: AgentChangeRequestBulkReview,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return approve_selected_change_requests(
        session,
        space_ctx,
        current_user,
        payload.change_request_ids,
        review_note=payload.review_note,
    )


@router.post(
    "/actions/reject-selected",
    response_model=AgentChangeRequestBulkReviewResult,
    operation_id="agent_reject_selected_change_requests",
    summary="Reject selected agent change requests",
)
def reject_selected_agent_change_requests(
    payload: AgentChangeRequestBulkReview,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return reject_selected_change_requests(
        session,
        space_ctx,
        current_user,
        payload.change_request_ids,
        review_note=payload.review_note,
    )
