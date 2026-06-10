from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import AgentChangeRequest, Project, Solution, Task, User
from ..routes._mutations import publish_space_mutation
from ..routes.projects.common import _project_query
from ..routes.solutions.common import _solution_query
from ..routes.tasks.common import _task_query
from ..schemas.agent import (
    AgentChangeRequestBulkReviewResult,
    AgentChangeRequestDiffItem,
    AgentChangeRequestListRead,
    AgentChangeRequestRead,
    AgentPatchOperation,
    AgentPatchRequest,
    AgentPatchResponse,
)
from ..services.agent_patch_plan import apply_patch_plan, validate_patch_plan
from ..services.spaces import SpaceContext
from ..utils import normalize_str

VALID_CHANGE_REQUEST_STATUSES = {"pending", "approved", "rejected", "failed"}


def _utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _json_default(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _dumps(value: Any) -> str:
    return json.dumps(value, default=_json_default, sort_keys=True)


def _loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _operation_payloads(payload: AgentPatchRequest) -> list[dict[str, Any]]:
    return [
        operation.model_dump(mode="json", exclude_none=True)
        for operation in payload.operations
    ]


def _stored_payload(row: AgentChangeRequest) -> AgentPatchRequest:
    return AgentPatchRequest(
        dry_run=False,
        reason=row.reason,
        idempotency_key=row.idempotency_key,
        operations=[
            AgentPatchOperation(**operation)
            for operation in _loads(row.operations_json, [])
        ],
    )


def _entity_label(row: Any, entity: str) -> str | None:
    if not row:
        return None
    if entity == "project":
        return getattr(row, "project_name", None)
    if entity == "solution":
        return getattr(row, "solution_name", None)
    if entity == "task":
        return getattr(row, "task_name", None)
    return None


def _entity_row(
    session: Session,
    space_ctx: SpaceContext,
    operation: AgentPatchOperation,
) -> Any:
    if operation.entity == "project" and operation.id:
        return (
            _project_query(session, space_ctx)
            .filter(Project.project_id == operation.id)
            .first()
        )
    if operation.entity == "solution" and operation.id:
        return (
            _solution_query(session, space_ctx)
            .filter(Solution.solution_id == operation.id)
            .first()
        )
    if operation.entity == "task" and operation.id:
        return (
            _task_query(session, space_ctx)
            .filter(Task.task_id == operation.id)
            .first()
        )
    return None


def build_patch_diff(
    session: Session,
    space_ctx: SpaceContext,
    payload: AgentPatchRequest,
) -> list[dict[str, Any]]:
    diff = []
    for operation in payload.operations:
        row = _entity_row(session, space_ctx, operation)
        fields = {}
        for field, new_value in operation.fields.items():
            old_value = None if operation.op == "create" else getattr(row, field, None)
            fields[field] = {
                "old": _enum_value(old_value),
                "new": _enum_value(new_value),
            }
        diff.append(
            AgentChangeRequestDiffItem(
                client_operation_id=operation.client_operation_id,
                op=operation.op,
                entity=operation.entity,
                entity_id=operation.id,
                entity_label=_entity_label(row, operation.entity),
                fields=fields,
            ).model_dump(mode="json")
        )
    return diff


def _proposer_label(row: AgentChangeRequest, users_by_id: dict[str, User]) -> str | None:
    user = users_by_id.get(row.proposed_by_user_id)
    if not user:
        return None
    return user.display_name or user.soeid or user.user_id


def _row_to_read(
    row: AgentChangeRequest,
    *,
    users_by_id: dict[str, User] | None = None,
) -> AgentChangeRequestRead:
    operations = [
        AgentPatchOperation(**operation)
        for operation in _loads(row.operations_json, [])
    ]
    validation_payload = _loads(row.validation_json, None)
    validation = (
        AgentPatchResponse(**validation_payload) if isinstance(validation_payload, dict) else None
    )
    return AgentChangeRequestRead(
        change_request_id=row.change_request_id,
        space_id=row.space_id,
        proposed_by_user_id=row.proposed_by_user_id,
        proposed_by_label=_proposer_label(row, users_by_id or {}),
        status=row.status,
        reason=row.reason,
        idempotency_key=row.idempotency_key,
        operation_count=len(operations),
        operations=operations,
        validation=validation,
        diff=[
            AgentChangeRequestDiffItem(**item)
            for item in _loads(row.diff_json, [])
        ],
        created_at=row.created_at,
        updated_at=row.updated_at,
        reviewed_by_user_id=row.reviewed_by_user_id,
        reviewed_at=row.reviewed_at,
        review_note=row.review_note,
        applied_at=row.applied_at,
        failed_reason=row.failed_reason,
    )


def _users_by_id(session: Session, rows: list[AgentChangeRequest]) -> dict[str, User]:
    user_ids = sorted({row.proposed_by_user_id for row in rows if row.proposed_by_user_id})
    if not user_ids:
        return {}
    users = session.query(User).filter(User.user_id.in_(user_ids)).all()
    return {user.user_id: user for user in users}


def _publish_change_requests(space_id: str) -> None:
    publish_space_mutation(
        space_id,
        ["agent_change_requests"],
        broadcast_channel="agent_change_requests",
    )


def create_change_request(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    payload: AgentPatchRequest,
) -> AgentChangeRequestRead:
    reason = normalize_str(payload.reason)
    idempotency_key = normalize_str(payload.idempotency_key)
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="reason is required",
        )
    if not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="idempotency_key is required",
        )
    effective_payload = AgentPatchRequest(
        dry_run=False,
        reason=reason,
        idempotency_key=idempotency_key,
        operations=payload.operations,
    )
    validation = validate_patch_plan(session, space_ctx, effective_payload)
    if not validation.valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation.model_dump(mode="json"),
        )
    diff = build_patch_diff(session, space_ctx, effective_payload)
    row = AgentChangeRequest(
        space_id=space_ctx.space_id,
        proposed_by_user_id=current_user.user_id,
        status="pending",
        reason=reason,
        idempotency_key=idempotency_key,
        operations_json=_dumps(_operation_payloads(effective_payload)),
        validation_json=validation.model_dump_json(),
        diff_json=_dumps(diff),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    _publish_change_requests(space_ctx.space_id)
    return _row_to_read(row, users_by_id={current_user.user_id: current_user})


def list_change_requests(
    session: Session,
    space_ctx: SpaceContext,
    *,
    status_filter: str = "pending",
    limit: int = 100,
) -> AgentChangeRequestListRead:
    normalized_status = normalize_str(status_filter).lower() or "pending"
    if normalized_status not in VALID_CHANGE_REQUEST_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid change request status",
        )
    query = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.status == normalized_status)
        .order_by(AgentChangeRequest.created_at.desc())
        .limit(limit)
    )
    rows = query.all()
    users = _users_by_id(session, rows)
    pending_count = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.status == "pending")
        .count()
    )
    failed_count = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.status == "failed")
        .count()
    )
    return AgentChangeRequestListRead(
        space_id=space_ctx.space_id,
        status=normalized_status,
        pending_count=pending_count,
        failed_count=failed_count,
        records=[_row_to_read(row, users_by_id=users) for row in rows],
    )


def get_change_request(
    session: Session,
    space_ctx: SpaceContext,
    change_request_id: str,
) -> AgentChangeRequestRead:
    row = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.change_request_id == change_request_id)
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent change request not found",
        )
    return _row_to_read(row, users_by_id=_users_by_id(session, [row]))


def approve_change_request(
    session: Session,
    space_ctx: SpaceContext,
    reviewer: User,
    change_request_id: str,
    *,
    review_note: str | None = None,
) -> AgentChangeRequestRead:
    row = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.change_request_id == change_request_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Agent change request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be approved")

    payload = _stored_payload(row)
    validation = validate_patch_plan(session, space_ctx, payload, for_apply=True)
    now = _utc_now_naive()
    row.reviewed_by_user_id = reviewer.user_id
    row.reviewed_at = now
    row.review_note = normalize_str(review_note) or None
    row.validation_json = validation.model_dump_json()
    row.diff_json = _dumps(build_patch_diff(session, space_ctx, payload))
    if not validation.valid:
        row.status = "failed"
        row.failed_reason = "Validation failed during approval"
        session.add(row)
        session.commit()
        session.refresh(row)
        _publish_change_requests(space_ctx.space_id)
        return _row_to_read(row, users_by_id=_users_by_id(session, [row]))

    apply_result = apply_patch_plan(session, space_ctx, reviewer, payload)
    if not apply_result.valid or not apply_result.applied:
        row.status = "failed"
        row.failed_reason = "Patch application failed"
    else:
        row.status = "approved"
        row.applied_at = _utc_now_naive()
        row.failed_reason = None
    row.validation_json = apply_result.model_dump_json()
    session.add(row)
    session.commit()
    session.refresh(row)
    _publish_change_requests(space_ctx.space_id)
    return _row_to_read(row, users_by_id=_users_by_id(session, [row]))


def reject_change_request(
    session: Session,
    space_ctx: SpaceContext,
    reviewer: User,
    change_request_id: str,
    *,
    review_note: str | None = None,
) -> AgentChangeRequestRead:
    row = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.change_request_id == change_request_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Agent change request not found")
    if row.status != "pending":
        raise HTTPException(status_code=400, detail="Only pending requests can be rejected")
    row.status = "rejected"
    row.reviewed_by_user_id = reviewer.user_id
    row.reviewed_at = _utc_now_naive()
    row.review_note = normalize_str(review_note) or None
    session.add(row)
    session.commit()
    session.refresh(row)
    _publish_change_requests(space_ctx.space_id)
    return _row_to_read(row, users_by_id=_users_by_id(session, [row]))


def approve_selected_change_requests(
    session: Session,
    space_ctx: SpaceContext,
    reviewer: User,
    change_request_ids: list[str],
    *,
    review_note: str | None = None,
) -> AgentChangeRequestBulkReviewResult:
    records = [
        approve_change_request(
            session,
            space_ctx,
            reviewer,
            change_request_id,
            review_note=review_note,
        )
        for change_request_id in change_request_ids
    ]
    return AgentChangeRequestBulkReviewResult(
        requested=len(change_request_ids),
        approved=sum(1 for record in records if record.status == "approved"),
        failed=sum(1 for record in records if record.status == "failed"),
        records=records,
    )


def reject_selected_change_requests(
    session: Session,
    space_ctx: SpaceContext,
    reviewer: User,
    change_request_ids: list[str],
    *,
    review_note: str | None = None,
) -> AgentChangeRequestBulkReviewResult:
    records = [
        reject_change_request(
            session,
            space_ctx,
            reviewer,
            change_request_id,
            review_note=review_note,
        )
        for change_request_id in change_request_ids
    ]
    return AgentChangeRequestBulkReviewResult(
        requested=len(change_request_ids),
        rejected=sum(1 for record in records if record.status == "rejected"),
        records=records,
    )
