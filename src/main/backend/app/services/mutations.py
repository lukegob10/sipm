from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .realtime import schedule_broadcast
from .smart_cache import invalidate_space

IntegrityErrorHandler = Callable[[IntegrityError], None]


def commit_session(
    session: Session,
    *,
    on_integrity_error: IntegrityErrorHandler | None = None,
) -> None:
    try:
        session.commit()
    except IntegrityError as err:
        session.rollback()
        if on_integrity_error is not None:
            on_integrity_error(err)
        raise


def publish_space_mutation(
    space_id: str,
    cache_keys: Sequence[str],
    *,
    broadcast_channel: str | None = None,
) -> None:
    invalidate_space(space_id, list(dict.fromkeys(cache_keys)))
    if broadcast_channel:
        schedule_broadcast(broadcast_channel, space_id=space_id)


def commit_refresh_and_publish(
    session: Session,
    instance: Any,
    *,
    space_id: str,
    cache_keys: Sequence[str],
    broadcast_channel: str | None = None,
    on_integrity_error: IntegrityErrorHandler | None = None,
) -> None:
    commit_session(session, on_integrity_error=on_integrity_error)
    session.refresh(instance)
    publish_space_mutation(
        space_id,
        cache_keys,
        broadcast_channel=broadcast_channel,
    )
