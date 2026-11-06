"""Reconcile retained raw telemetry into daily rollups during an offline maintenance window."""

from __future__ import annotations

from datetime import datetime
from itertools import islice

from sqlalchemy import case, func, literal, select, union
from sqlalchemy.orm import Session

from ..models import PerformanceSample, UsageDailyRollup, UsageEvent, UsageIdentityDailyRollup, UsageRouteIdentityDailyRollup
from .usage_analytics import _FAILURE_OUTCOMES, _UNSCOPED_SPACE_ID, _bucket_to_date, _date_bucket_expr, _load_existing_rollups

_BATCH_SIZE = 100
_EVENT_KEYS = ("rollup_date", "space_id", "view_key", "category", "feature_key", "action_key", "outcome")
_IDENTITY_KEYS = ("rollup_date", "space_id", "token_type", "token_value")
_ROUTE_IDENTITY_KEYS = ("rollup_date", "space_id", "view_key", "token_type", "token_value")


def _space_expr(column):
    trimmed = func.trim(column)
    return case((func.length(trimmed) > 0, trimmed), else_=literal(_UNSCOPED_SPACE_ID))


def _batches(rows):
    iterator = iter(rows)
    while batch := list(islice(iterator, _BATCH_SIZE)):
        yield batch


def _identity_select(session, model, token_name: str, token_type: str, *, since: datetime, until: datetime, route: bool):
    token = getattr(model, token_name)
    columns = [
        _date_bucket_expr(session, model.occurred_at).label("rollup_date"),
        _space_expr(model.space_id).label("space_id"),
    ]
    if route:
        columns.append(model.view_key.label("view_key"))
    columns.extend([literal(token_type).label("token_type"), token.label("token_value")])
    filters = [model.occurred_at >= since, model.occurred_at < until, token.is_not(None), func.length(token) > 0]
    if route:
        filters.append(model.action_key == "route_view")
    return select(*columns).where(*filters)


def _event_group_statement(session: Session, *, since: datetime, until: datetime):
    bucket = _date_bucket_expr(session, UsageEvent.occurred_at)
    space = _space_expr(UsageEvent.space_id)
    dimensions = (bucket, space, UsageEvent.view_key, UsageEvent.category,
                  UsageEvent.feature_key, UsageEvent.action_key, UsageEvent.outcome)
    return (
        select(*dimensions, func.count().label("total"), func.max(UsageEvent.occurred_at).label("last_occurred_at"))
        .where(UsageEvent.occurred_at >= since, UsageEvent.occurred_at < until)
        .group_by(*dimensions)
    )


def backfill_usage_rollups(session: Session, *, since: datetime, until: datetime, apply: bool = False) -> dict[str, int]:
    """Reconcile a complete retained-raw window; ingestion must be paused for the entire transaction.

    Existing larger aggregates are preserved because their raw records may have been purged.
    The caller owns the transaction and decides whether to commit or roll it back.
    """
    if (since.tzinfo is not None or until.tzinfo is not None or since >= until
            or since.time() != datetime.min.time() or until.time() != datetime.min.time()):
        raise ValueError("since and until must be ordered, naive UTC midnight boundaries")
    counts = {"event_groups_created": 0, "event_groups_updated": 0, "larger_rollups_preserved": 0,
              "identities_created": 0, "route_identities_created": 0}
    rows = session.execute(_event_group_statement(session, since=since, until=until)).yield_per(_BATCH_SIZE)
    for batch in _batches(rows):
        keys = [(_bucket_to_date(row[0]), *tuple(row[1:7])) for row in batch]
        existing = _load_existing_rollups(session, UsageDailyRollup, key_columns=_EVENT_KEYS, keys=keys)
        for key, row in zip(keys, batch):
            total, last = int(row[7]), row[8]
            current = existing.get(key)
            if current is not None and current.event_count > total:
                counts["larger_rollups_preserved"] += 1
                if last > current.last_occurred_at:
                    counts["event_groups_updated"] += 1
                    if apply:
                        current.last_occurred_at = last
                continue
            values = {
                "event_count": total,
                "route_view_count": total if key[5] == "route_view" else 0,
                "workflow_action_count": total if key[3] == "workflow" else 0,
                "success_count": total if key[6] == "success" else 0,
                "failure_count": total if key[6] in _FAILURE_OUTCOMES else 0,
                "last_occurred_at": max(current.last_occurred_at, last) if current is not None else last,
            }
            if current is None:
                counts["event_groups_created"] += 1
                if apply:
                    session.add(UsageDailyRollup(**dict(zip(_EVENT_KEYS, key)), **values))
            elif any(getattr(current, field) != value for field, value in values.items()):
                counts["event_groups_updated"] += 1
                if apply:
                    for field, value in values.items():
                        setattr(current, field, value)
        if apply:
            session.flush()

    for route, model, columns, count_key in (
        (False, UsageIdentityDailyRollup, _IDENTITY_KEYS, "identities_created"),
        (True, UsageRouteIdentityDailyRollup, _ROUTE_IDENTITY_KEYS, "route_identities_created"),
    ):
        sources = (UsageEvent,) if route else (UsageEvent, PerformanceSample)
        statement = union(*(
            _identity_select(session, source, name, token_type, since=since, until=until, route=route)
            for source in sources for name, token_type in (("session_id", "session"), ("user_id", "user"))
        ))
        rows = session.execute(statement).yield_per(_BATCH_SIZE)
        for batch in _batches(rows):
            keys = [(_bucket_to_date(row[0]), *tuple(row[1:])) for row in batch]
            existing = _load_existing_rollups(session, model, key_columns=columns, keys=keys)
            for key in keys:
                if key not in existing:
                    counts[count_key] += 1
                    if apply:
                        session.add(model(**dict(zip(columns, key))))
            if apply:
                session.flush()
    return counts
