from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from ...deps import (
    current_agent_space,
    current_agent_or_user_space,
    current_delegated_human_space,
    current_space as current_space_dep,
    get_db,
    require_agent_or_interactive_user,
    require_agent_or_user_space_role,
    require_agent_service_account,
    require_human_delegated_token,
    require_delegated_human_space_role,
    require_interactive_user,
    require_space_role,
)
from ...models import User
from ...schemas.agent import (
    AgentChangeRequestBulkReview,
    AgentChangeRequestBulkReviewResult,
    AgentChangeRequestListRead,
    AgentChangeRequestOperationReview,
    AgentChangeRequestRead,
    AgentChangeRequestReview,
    AgentChangeRequestUpdate,
    AgentDelegatedChangeRequestReview,
    AgentPatchRequest,
)
from ...services.agent_change_requests import (
    approve_change_request,
    approve_change_request_operations,
    approve_selected_change_requests,
    cancel_change_request,
    create_change_request,
    get_change_request,
    list_change_requests,
    reject_change_request,
    reject_selected_change_requests,
    update_change_request,
    verify_delegated_review_confirmation,
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
    request: Request,
    status: str = "pending",
    idempotency_key: str | None = None,
    created_since: datetime | None = None,
    updated_since: datetime | None = None,
    cursor: str | None = None,
    limit: int = Query(100, ge=1, le=200),
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_interactive_user),
    space_ctx: SpaceContext = Depends(current_agent_or_user_space),
    _authz: SpaceContext = Depends(require_agent_or_user_space_role("member")),
):
    proposed_by_user_id = (
        current_user.user_id
        if getattr(request.state, "auth_method", None) == "api_token"
        and getattr(current_user, "is_service_account", False)
        else None
    )
    return list_change_requests(
        session,
        space_ctx,
        status_filter=status,
        proposed_by_user_id=proposed_by_user_id,
        idempotency_key=idempotency_key,
        created_since=created_since,
        updated_since=updated_since,
        limit=limit,
        cursor=cursor,
    )


@router.get(
    "/{change_request_id}",
    response_model=AgentChangeRequestRead,
    operation_id="agent_get_change_request",
    summary="Get agent change request",
)
def get_agent_change_request(
    change_request_id: str,
    request: Request,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_or_interactive_user),
    space_ctx: SpaceContext = Depends(current_agent_or_user_space),
    _authz: SpaceContext = Depends(require_agent_or_user_space_role("member")),
):
    proposed_by_user_id = (
        current_user.user_id
        if getattr(request.state, "auth_method", None) == "api_token"
        and getattr(current_user, "is_service_account", False)
        else None
    )
    return get_change_request(
        session,
        space_ctx,
        change_request_id,
        proposed_by_user_id=proposed_by_user_id,
    )


@router.put(
    "/{change_request_id}",
    response_model=AgentChangeRequestRead,
    operation_id="agent_update_change_request",
    summary="Replace an owned pending agent change request in place",
)
def update_agent_change_request(
    change_request_id: str,
    payload: AgentChangeRequestUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_service_account),
    space_ctx: SpaceContext = Depends(current_agent_space),
):
    return update_change_request(
        session,
        space_ctx,
        current_user,
        change_request_id,
        payload,
    )


@router.get(
    "/{change_request_id}/delegated-review",
    response_model=AgentChangeRequestRead,
    operation_id="agent_get_delegated_change_request_review",
    summary="Retrieve an immutable request diff as an authenticated human delegate",
)
def get_delegated_agent_change_request_review(
    change_request_id: str,
    session: Session = Depends(get_db),
    _current_user: User = Depends(require_human_delegated_token),
    space_ctx: SpaceContext = Depends(current_delegated_human_space),
    _authz: SpaceContext = Depends(require_delegated_human_space_role("member")),
):
    return get_change_request(session, space_ctx, change_request_id)


@router.post(
    "/{change_request_id}/cancel",
    response_model=AgentChangeRequestRead,
    operation_id="agent_cancel_change_request",
    summary="Cancel an owned pending agent change request",
)
def cancel_agent_change_request(
    change_request_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_agent_service_account),
    space_ctx: SpaceContext = Depends(current_agent_space),
):
    return cancel_change_request(
        session,
        space_ctx,
        current_user,
        change_request_id,
    )


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
    "/{change_request_id}/delegated-approve",
    response_model=AgentChangeRequestRead,
    operation_id="agent_delegated_approve_change_request",
    summary="Approve a reviewed request as an authenticated human delegate",
)
def delegated_approve_agent_change_request(
    change_request_id: str,
    payload: AgentDelegatedChangeRequestReview,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_human_delegated_token),
    space_ctx: SpaceContext = Depends(current_delegated_human_space),
    _authz: SpaceContext = Depends(require_delegated_human_space_role("member")),
):
    verify_delegated_review_confirmation(
        session,
        space_ctx,
        change_request_id,
        confirmed_change_request_id=payload.confirm_change_request_id,
        if_request_updated_at=payload.if_request_updated_at,
    )
    return approve_change_request(
        session,
        space_ctx,
        current_user,
        change_request_id,
        review_note=payload.review_note,
    )


@router.post(
    "/{change_request_id}/approve-selected-operations",
    response_model=AgentChangeRequestRead,
    operation_id="agent_approve_selected_change_request_operations",
    summary="Approve and apply selected operations from an agent change request",
)
def approve_selected_agent_change_request_operations(
    change_request_id: str,
    payload: AgentChangeRequestOperationReview,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_interactive_user),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
):
    return approve_change_request_operations(
        session,
        space_ctx,
        current_user,
        change_request_id,
        payload.client_operation_ids,
        review_note=payload.review_note,
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
    "/{change_request_id}/delegated-reject",
    response_model=AgentChangeRequestRead,
    operation_id="agent_delegated_reject_change_request",
    summary="Reject a reviewed request as an authenticated human delegate",
)
def delegated_reject_agent_change_request(
    change_request_id: str,
    payload: AgentDelegatedChangeRequestReview,
    session: Session = Depends(get_db),
    current_user: User = Depends(require_human_delegated_token),
    space_ctx: SpaceContext = Depends(current_delegated_human_space),
    _authz: SpaceContext = Depends(require_delegated_human_space_role("member")),
):
    verify_delegated_review_confirmation(
        session,
        space_ctx,
        change_request_id,
        confirmed_change_request_id=payload.confirm_change_request_id,
        if_request_updated_at=payload.if_request_updated_at,
    )
    return reject_change_request(
        session,
        space_ctx,
        current_user,
        change_request_id,
        review_note=payload.review_note,
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
