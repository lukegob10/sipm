from datetime import datetime, timezone
from typing import Dict, Optional, Any
from uuid import uuid4

from ..models import ChangeLog


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
    return str(value)


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
    if changes:
        for field, pair in changes.items():
            if not isinstance(pair, tuple) or len(pair) != 2:
                continue
            old, new = pair
            if old == new:
                continue
            rows.append(
                ChangeLog(
                    change_id=str(uuid4()),
                    entity_type=entity_type,
                    entity_id=entity_id,
                    action=action,
                    field=field,
                    old_value=_stringify(old),
                    new_value=_stringify(new),
                    user_id=user_id,
                    space_id=space_id,
                    request_id=request_id,
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
                request_id=request_id,
                created_at=now,
            )
        )
    if not rows:
        return
    for row in rows:
        session.add(row)
