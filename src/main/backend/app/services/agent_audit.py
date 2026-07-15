from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models import ChangeLog
from ..schemas.agent import AgentAuditFeedRead, AgentAuditRecordRead
from .agent_pagination import decode_cursor, encode_cursor
from .spaces import SpaceContext

AUDIT_CURSOR_SCOPE = "agent_audit_v1"


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def list_agent_audit_feed(
    session: Session,
    space_ctx: SpaceContext,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    user_id: str | None = None,
    request_id: str | None = None,
    cursor: str | None = None,
    limit: int = 100,
) -> AgentAuditFeedRead:
    since_value = _utc_naive(since) if since else None
    until_value = _utc_naive(until) if until else None
    filters = {
        "space_id": space_ctx.space_id,
        "since": since_value,
        "until": until_value,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "user_id": user_id,
        "request_id": request_id,
    }
    query = session.query(ChangeLog).filter(ChangeLog.space_id == space_ctx.space_id)
    if since_value:
        query = query.filter(ChangeLog.created_at >= since_value)
    if until_value:
        query = query.filter(ChangeLog.created_at <= until_value)
    if entity_type:
        query = query.filter(ChangeLog.entity_type == entity_type)
    if entity_id:
        query = query.filter(ChangeLog.entity_id == entity_id)
    if user_id:
        query = query.filter(ChangeLog.user_id == user_id)
    if request_id:
        query = query.filter(ChangeLog.request_id == request_id)
    if cursor:
        cursor_at, cursor_id = decode_cursor(
            cursor, scope=AUDIT_CURSOR_SCOPE, filters=filters
        )
        cursor_at = _utc_naive(cursor_at)
        query = query.filter(
            or_(
                ChangeLog.created_at < cursor_at,
                and_(
                    ChangeLog.created_at == cursor_at, ChangeLog.change_id < cursor_id
                ),
            )
        )
    rows = (
        query.order_by(ChangeLog.created_at.desc(), ChangeLog.change_id.desc())
        .limit(limit + 1)
        .all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = None
    if has_more and rows:
        next_cursor = encode_cursor(
            scope=AUDIT_CURSOR_SCOPE,
            filters=filters,
            ordered_at=rows[-1].created_at,
            ordered_id=rows[-1].change_id,
        )
    return AgentAuditFeedRead(
        space_id=space_ctx.space_id,
        records=[AgentAuditRecordRead.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )
