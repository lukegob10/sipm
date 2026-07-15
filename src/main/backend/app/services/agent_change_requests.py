from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models import AgentChangeRequest, Program, Project, Solution, Task, User
from ..schemas.agent import (
    AgentChangeRequestBulkReviewResult,
    AgentChangeRequestDiffItem,
    AgentChangeRequestListRead,
    AgentChangeRequestRead,
    AgentPatchOperation,
    AgentPatchRequest,
    AgentPatchResponse,
)
from ..security import security_http_exception
from ..services.audit_log import log_changes
from ..services.agent_patch_plan import apply_patch_plan, validate_patch_plan
from ..services.agent_pagination import decode_cursor, encode_cursor
from ..services.mutations import publish_space_mutation
from ..services.spaces import SpaceContext
from ..services.work_items import (
    project_query as _project_query,
    solution_query as _solution_query,
    task_query as _task_query,
)
from ..services.programs import program_query as _program_query
from ..utils import normalize_str

VALID_CHANGE_REQUEST_STATUSES = {
    "pending",
    "approved",
    "rejected",
    "failed",
    "cancelled",
}
CHANGE_REQUEST_CURSOR_SCOPE = "agent_change_requests_v1"


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


def _same_idempotent_request(
    row: AgentChangeRequest,
    *,
    reason: str,
    operations_json: str,
) -> bool:
    return row.reason == reason and row.operations_json == operations_json


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
    if entity == "program":
        return getattr(row, "program_name", None)
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
    if operation.entity == "program" and operation.id:
        return (
            _program_query(session, space_ctx)
            .filter(Program.program_id == operation.id)
            .first()
        )
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
        if operation.op == "archive":
            fields["lifecycle"] = {"old": "active", "new": "archived"}
            if operation.entity in {"project", "solution"}:
                fields["descendant_visibility"] = {
                    "old": "accessible",
                    "new": "inaccessible_with_parent",
                }
        diff.append(
            AgentChangeRequestDiffItem(
                client_operation_id=operation.client_operation_id,
                op=operation.op,
                entity=operation.entity,
                entity_id=operation.id,
                entity_ref=operation.ref,
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
    operations_json = _dumps(_operation_payloads(effective_payload))
    existing = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.proposed_by_user_id == current_user.user_id)
        .filter(AgentChangeRequest.idempotency_key == idempotency_key)
        .order_by(AgentChangeRequest.created_at.desc())
        .first()
    )
    if existing:
        if _same_idempotent_request(
            existing,
            reason=reason,
            operations_json=operations_json,
        ):
            return _row_to_read(existing, users_by_id={current_user.user_id: current_user})
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="idempotency_key has already been used with a different request",
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
        operations_json=operations_json,
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
    proposed_by_user_id: str | None = None,
    idempotency_key: str | None = None,
    created_since: datetime | None = None,
    updated_since: datetime | None = None,
    limit: int = 100,
    cursor: str | None = None,
) -> AgentChangeRequestListRead:
    requested_status = normalize_str(status_filter).lower() or "pending"
    statuses = (
        sorted(VALID_CHANGE_REQUEST_STATUSES)
        if requested_status == "all"
        else sorted(
            {
                normalize_str(item).lower()
                for item in requested_status.split(",")
                if normalize_str(item)
            }
        )
    )
    if not statuses or any(item not in VALID_CHANGE_REQUEST_STATUSES for item in statuses):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid change request status",
        )
    base_query = session.query(AgentChangeRequest).filter(
        AgentChangeRequest.space_id == space_ctx.space_id
    )
    if proposed_by_user_id:
        base_query = base_query.filter(
            AgentChangeRequest.proposed_by_user_id == proposed_by_user_id
        )

    normalized_idempotency_key = normalize_str(idempotency_key) or None
    query = base_query.filter(AgentChangeRequest.status.in_(statuses))
    if normalized_idempotency_key:
        query = query.filter(
            AgentChangeRequest.idempotency_key == normalized_idempotency_key
        )
    if created_since:
        query = query.filter(AgentChangeRequest.created_at >= created_since)
    if updated_since:
        query = query.filter(AgentChangeRequest.updated_at >= updated_since)

    cursor_filters = {
        "space_id": space_ctx.space_id,
        "proposed_by_user_id": proposed_by_user_id,
        "statuses": statuses,
        "idempotency_key": normalized_idempotency_key,
        "created_since": created_since.isoformat() if created_since else None,
        "updated_since": updated_since.isoformat() if updated_since else None,
    }
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(
            cursor,
            scope=CHANGE_REQUEST_CURSOR_SCOPE,
            filters=cursor_filters,
        )
        query = query.filter(
            or_(
                AgentChangeRequest.created_at < cursor_created_at,
                and_(
                    AgentChangeRequest.created_at == cursor_created_at,
                    AgentChangeRequest.change_request_id < cursor_id,
                ),
            )
        )

    rows = (
        query.order_by(
            AgentChangeRequest.created_at.desc(),
            AgentChangeRequest.change_request_id.desc(),
        )
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        last_row = rows[-1]
        next_cursor = encode_cursor(
            scope=CHANGE_REQUEST_CURSOR_SCOPE,
            filters=cursor_filters,
            ordered_at=last_row.created_at,
            ordered_id=last_row.change_request_id,
        )

    users = _users_by_id(session, rows)
    pending_count = (
        base_query.filter(AgentChangeRequest.status == "pending").count()
    )
    failed_count = base_query.filter(AgentChangeRequest.status == "failed").count()
    return AgentChangeRequestListRead(
        space_id=space_ctx.space_id,
        status=requested_status,
        pending_count=pending_count,
        failed_count=failed_count,
        records=[_row_to_read(row, users_by_id=users) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


def get_change_request(
    session: Session,
    space_ctx: SpaceContext,
    change_request_id: str,
    *,
    proposed_by_user_id: str | None = None,
) -> AgentChangeRequestRead:
    query = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
    )
    if proposed_by_user_id:
        query = query.filter(
            AgentChangeRequest.proposed_by_user_id == proposed_by_user_id
        )
    row = query.filter(
        AgentChangeRequest.change_request_id == change_request_id
    ).first()
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


def verify_delegated_review_confirmation(
    session: Session,
    space_ctx: SpaceContext,
    change_request_id: str,
    *,
    confirmed_change_request_id: str,
    if_request_updated_at: datetime,
) -> None:
    if normalize_str(confirmed_change_request_id) != change_request_id:
        raise security_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            code="CONFIRMATION_REQUEST_MISMATCH",
            message="Confirmation does not match the requested change request",
        )
    row = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.change_request_id == change_request_id)
        .first()
    )
    if row is None:
        raise security_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CHANGE_REQUEST_NOT_FOUND",
            message="Agent change request not found",
        )
    current = row.updated_at
    expected = if_request_updated_at
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    if expected.tzinfo is not None:
        expected = expected.astimezone(timezone.utc).replace(tzinfo=None)
    if current != expected:
        raise security_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            code="CHANGE_REQUEST_CHANGED",
            message="Change request changed after it was reviewed",
        )
    if row.status != "pending":
        raise security_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            code="CHANGE_REQUEST_NOT_PENDING",
            message="Only pending change requests can be reviewed",
        )


def cancel_change_request(
    session: Session,
    space_ctx: SpaceContext,
    proposer: User,
    change_request_id: str,
) -> AgentChangeRequestRead:
    row = (
        session.query(AgentChangeRequest)
        .filter(AgentChangeRequest.space_id == space_ctx.space_id)
        .filter(AgentChangeRequest.proposed_by_user_id == proposer.user_id)
        .filter(AgentChangeRequest.change_request_id == change_request_id)
        .first()
    )
    if not row:
        raise security_http_exception(
            status_code=status.HTTP_404_NOT_FOUND,
            code="CHANGE_REQUEST_NOT_FOUND",
            message="Agent change request not found",
        )
    if row.status == "cancelled":
        return _row_to_read(row, users_by_id={proposer.user_id: proposer})
    if row.status != "pending":
        raise security_http_exception(
            status_code=status.HTTP_409_CONFLICT,
            code="CHANGE_REQUEST_NOT_PENDING",
            message="Only pending change requests can be cancelled",
        )

    previous_status = row.status
    row.status = "cancelled"
    session.add(row)
    log_changes(
        session,
        entity_type="agent_change_request",
        entity_id=row.change_request_id,
        user_id=proposer.user_id,
        action="cancel",
        changes={"status": (previous_status, row.status)},
        space_id=space_ctx.space_id,
    )
    session.commit()
    session.refresh(row)
    _publish_change_requests(space_ctx.space_id)
    return _row_to_read(row, users_by_id={proposer.user_id: proposer})


def approve_change_request_operations(
    session: Session,
    space_ctx: SpaceContext,
    reviewer: User,
    change_request_id: str,
    client_operation_ids: list[str],
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

    selected_ids = [normalize_str(value) for value in client_operation_ids]
    if any(not value for value in selected_ids) or len(set(selected_ids)) != len(selected_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="client_operation_ids must be unique, non-empty values",
        )

    original_payload = _stored_payload(row)
    operations_by_id = {
        operation.client_operation_id: operation
        for operation in original_payload.operations
    }
    unknown_ids = [value for value in selected_ids if value not in operations_by_id]
    if unknown_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"unknown_client_operation_ids": unknown_ids},
        )

    selected_payload = AgentPatchRequest(
        dry_run=False,
        reason=original_payload.reason,
        idempotency_key=original_payload.idempotency_key,
        operations=[operations_by_id[value] for value in selected_ids],
    )
    validation = validate_patch_plan(session, space_ctx, selected_payload, for_apply=True)
    now = _utc_now_naive()
    row.reviewed_by_user_id = reviewer.user_id
    row.reviewed_at = now
    row.review_note = normalize_str(review_note) or None
    row.validation_json = validation.model_dump_json()
    if not validation.valid:
        row.status = "failed"
        row.failed_reason = "Validation failed during approval"
        session.add(row)
        session.commit()
        session.refresh(row)
        _publish_change_requests(space_ctx.space_id)
        return _row_to_read(row, users_by_id=_users_by_id(session, [row]))

    apply_result = apply_patch_plan(session, space_ctx, reviewer, selected_payload)
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
