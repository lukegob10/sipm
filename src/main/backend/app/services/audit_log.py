import logging
from datetime import datetime, timezone
from typing import Dict, Optional, Any
from uuid import uuid4

from ..models import ChangeLog
from ..request_context import get_request_id
from ..utils import read_text_value

logger = logging.getLogger(__name__)


def _stringify(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):  # enums
        value = value.value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            return str(value)
    return read_text_value(value)


def log_changes(
    session,
    *,
    entity_type: str,
    entity_id: str,
    user_id: str,
    action: str,
    changes: Optional[Dict[str, tuple]] = None,
    request_id: Optional[str] = None,
    space_id: Optional[str] = None,
) -> None:
    """
    Append rows to change_log within the caller's transaction.
    - action: create|update|delete|restore (string)
    - changes: dict[field] = (old, new); ignored if old == new
    """
    rows = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    effective_request_id = request_id if request_id is not None else get_request_id()
    if changes:
        for field, pair in changes.items():
            if not isinstance(pair, tuple) or len(pair) != 2:
                continue
            old, new = pair
            old_value = _stringify(old)
            new_value = _stringify(new)
            if old_value == new_value:
                continue
            rows.append(
                ChangeLog(
                    change_id=str(uuid4()),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action=action,
                    field=field,
                    old_value=old_value,
                    new_value=new_value,
                    user_id=user_id,
                    space_id=space_id,
                    request_id=effective_request_id,
                    created_at=now,
                )
            )
    else:
        rows.append(
            ChangeLog(
                change_id=str(uuid4()),
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                field=None,
                old_value=None,
                new_value=None,
                user_id=user_id,
                space_id=space_id,
                request_id=effective_request_id,
                created_at=now,
            )
        )
    if not rows:
        return
    for row in rows:
        session.add(row)


def safe_log_changes(session, **kwargs) -> None:
    """Best-effort audit logging that cannot abort the caller's primary write."""
    try:
        with session.begin_nested():
            log_changes(session, **kwargs)
            session.flush()
    except Exception:
        logger.warning("Audit log write skipped after database error", exc_info=True)
