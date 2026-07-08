from __future__ import annotations

import json
import math
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, Optional

from fastapi import Query
from sqlalchemy import case, func, inspect, literal, or_, select, union

from ..db.table_names import physical_table_name
from ..models import (
    PerformanceSample,
    Space,
    UsageDailyRollup,
    UsageEvent,
    UsageIdentityDailyRollup,
    UsageRouteIdentityDailyRollup,
)
from ..security import security_http_exception


_ALLOWED_WINDOW_DAYS = {7, 30, 90}
_MAX_BATCH_SIZE = 100
_MAX_DETAILS_BYTES = 1024
_MAX_DETAIL_VALUE_LENGTH = 160
_MAX_DURATION_MS = 24 * 60 * 60 * 1000
_SCHEMA_CHECK_TTL_SECONDS = 30
_FAILURE_OUTCOMES = ("failure", "timeout", "server_error")
_UNSCOPED_SPACE_ID = "__none__"
_PERSONAL_SPACE_KIND = "personal"
_SCHEMA_AVAILABILITY_CACHE: dict[tuple[str, str], float] = {}

ALLOWED_EVENT_CATEGORIES = {"lifecycle", "navigation", "workflow", "operations"}
ALLOWED_FEATURE_KEYS = {
    "analytics",
    "app",
    "csv",
    "navigation",
    "planning",
    "projects",
    "spaces",
    "tasks",
    "solutions",
    "teams",
    "users",
}
ALLOWED_ACTION_KEYS = {
    "api_failure",
    "app_boot",
    "assignment_create",
    "assignment_delete",
    "assignment_update",
    "create",
    "delete",
    "export",
    "import",
    "module_load_failure",
    "report_download",
    "route_transition_complete",
    "route_view",
    "space_switch",
    "switch",
    "update",
}
ALLOWED_OUTCOMES = {"success", "failure", "timeout", "server_error"}
ALLOWED_SAMPLE_KINDS = {"navigation", "route_transition"}
ALLOWED_NAVIGATION_TYPES = {"navigate", "reload", "back_forward", "prerender"}
ALLOWED_DETAIL_KEYS = {
    "all_spaces",
    "error_kind",
    "kind",
    "navigation_type",
    "path",
    "path_group",
    "previous_view",
    "result_kind",
    "scope",
    "source",
    "status_family",
    "target_view",
}


def _env_bool(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def usage_analytics_enabled() -> bool:
    return _env_bool("SIPM_USAGE_ANALYTICS_ENABLED", False)


def validate_window_days(days: int) -> int:
    if days not in _ALLOWED_WINDOW_DAYS:
        raise security_http_exception(
            status_code=400,
            code="INVALID_ANALYTICS_WINDOW",
            message="days must be one of 7, 30, or 90",
        )
    return days


def analytics_window_days_query(default: int = 30) -> int:
    return Query(default=default, ge=min(_ALLOWED_WINDOW_DAYS), le=max(_ALLOWED_WINDOW_DAYS))


def ensure_usage_analytics_available(session) -> None:
    if not usage_analytics_enabled():
        raise security_http_exception(
            status_code=404,
            code="USAGE_ANALYTICS_DISABLED",
            message="Usage analytics is not enabled",
        )
    bind = session.get_bind()
    cache_key = (bind.dialect.name, str(bind.url))
    now = time.monotonic()
    cached_until = _SCHEMA_AVAILABILITY_CACHE.get(cache_key)
    if cached_until and cached_until > now:
        return
    inspector = inspect(bind)
    required_tables = [
        physical_table_name("usage_events"),
        physical_table_name("performance_samples"),
        physical_table_name("usage_daily_rollups"),
        physical_table_name("usage_identity_daily_rollups"),
        physical_table_name("usage_route_identity_daily_rollups"),
    ]
    for table_name in required_tables:
        if not inspector.has_table(table_name):
            _SCHEMA_AVAILABILITY_CACHE.pop(cache_key, None)
            raise security_http_exception(
                status_code=503,
                code="USAGE_ANALYTICS_SCHEMA_MISSING",
                message="Usage analytics schema is not available",
            )
    _SCHEMA_AVAILABILITY_CACHE[cache_key] = now + _SCHEMA_CHECK_TTL_SECONDS


def sanitize_details(value: object) -> Optional[str]:
    if not isinstance(value, dict):
        return None
    clean: dict[str, str | int | float | bool | None] = {}
    for raw_key, raw_val in value.items():
        key = str(raw_key or "").strip().lower().replace(" ", "_").replace("-", "_")
        if key not in ALLOWED_DETAIL_KEYS:
            continue
        if raw_val is None or isinstance(raw_val, bool):
            clean[key] = raw_val
            continue
        if isinstance(raw_val, int):
            clean[key] = raw_val
            continue
        if isinstance(raw_val, float):
            if math.isfinite(raw_val):
                clean[key] = round(raw_val, 4)
            continue
        text = str(raw_val or "").strip()
        if not text:
            continue
        clean[key] = text[:_MAX_DETAIL_VALUE_LENGTH]
    if not clean:
        return None
    raw = json.dumps(clean, sort_keys=True, separators=(",", ":"))
    if len(raw.encode("utf-8")) > _MAX_DETAILS_BYTES:
        raise security_http_exception(
            status_code=400,
            code="ANALYTICS_DETAILS_TOO_LARGE",
            message="Analytics details payload is too large",
        )
    return raw


def normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def validate_usage_event_payload(event) -> None:
    if event.category not in ALLOWED_EVENT_CATEGORIES:
        raise security_http_exception(
            status_code=400,
            code="INVALID_ANALYTICS_CATEGORY",
            message="Invalid analytics category",
        )
    if event.feature_key not in ALLOWED_FEATURE_KEYS:
        raise security_http_exception(
            status_code=400,
            code="INVALID_ANALYTICS_FEATURE",
            message="Invalid analytics feature",
        )
    if event.action_key not in ALLOWED_ACTION_KEYS:
        raise security_http_exception(
            status_code=400,
            code="INVALID_ANALYTICS_ACTION",
            message="Invalid analytics action",
        )
    if event.outcome not in ALLOWED_OUTCOMES:
        raise security_http_exception(
            status_code=400,
            code="INVALID_ANALYTICS_OUTCOME",
            message="Invalid analytics outcome",
        )
    if event.duration_ms is not None and not (0 <= int(event.duration_ms) <= _MAX_DURATION_MS):
        raise security_http_exception(
            status_code=400,
            code="INVALID_ANALYTICS_DURATION",
            message="Invalid analytics duration",
        )


def validate_performance_sample_payload(sample) -> None:
    if sample.sample_kind not in ALLOWED_SAMPLE_KINDS:
        raise security_http_exception(
            status_code=400,
            code="INVALID_SAMPLE_KIND",
            message="Invalid performance sample kind",
        )
    if sample.navigation_type and sample.navigation_type not in ALLOWED_NAVIGATION_TYPES:
        raise security_http_exception(
            status_code=400,
            code="INVALID_NAVIGATION_TYPE",
            message="Invalid navigation type",
        )


def enforce_batch_limits(events_count: int, performance_count: int) -> None:
    total = int(events_count) + int(performance_count)
    if total > _MAX_BATCH_SIZE:
        raise security_http_exception(
            status_code=400,
            code="ANALYTICS_BATCH_TOO_LARGE",
            message=f"Analytics batch may contain at most {_MAX_BATCH_SIZE} items",
        )


def scope_space_id_for_request(*, current_space_id: str, all_spaces: bool, requested_space_id: str | None) -> str | None:
    if all_spaces:
        return None
    requested = str(requested_space_id or "").strip()
    if requested:
        return requested
    return current_space_id


def validate_requested_analytics_space(session, *, scope_space_id: str | None) -> None:
    if not scope_space_id:
        return
    exists = (
        session.query(Space.space_id)
        .filter(Space.space_id == scope_space_id)
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active == True)
        .first()
    )
    if exists:
        return
    raise security_http_exception(
        status_code=404,
        code="ANALYTICS_SPACE_NOT_FOUND",
        message="Analytics space was not found",
    )


def analytics_window_start(days: int) -> datetime:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=max(days - 1, 0))
    return datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc).replace(tzinfo=None)


def analytics_scope_read(*, days: int, all_spaces: bool, scope_space_id: str | None) -> dict:
    return {
        "days": days,
        "all_spaces": all_spaces,
        "scope_space_id": scope_space_id,
        "generated_at": datetime.now(timezone.utc).replace(tzinfo=None),
    }


def _non_personal_space_ids_select():
    return select(Space.space_id).where(
        Space.deleted_at.is_(None),
        or_(Space.space_kind.is_(None), Space.space_kind != _PERSONAL_SPACE_KIND),
    )


def _base_filters(model, *, since: datetime, scope_space_id: str | None) -> list:
    filters = [model.occurred_at >= since]
    if scope_space_id:
        filters.append(model.space_id == scope_space_id)
    else:
        filters.append(
            or_(
                model.space_id.is_(None),
                model.space_id == "",
                model.space_id.in_(_non_personal_space_ids_select()),
            )
        )
    return filters


def _rollup_space_id(space_id: str | None) -> str:
    return str(space_id or "").strip() or _UNSCOPED_SPACE_ID


def _rollup_space_filter(model, *, scope_space_id: str | None) -> list:
    if scope_space_id:
        return [model.space_id == _rollup_space_id(scope_space_id)]
    return [
        or_(
            model.space_id == _UNSCOPED_SPACE_ID,
            model.space_id.in_(_non_personal_space_ids_select()),
        )
    ]


def _rollup_date_filters(model, *, since: datetime, scope_space_id: str | None) -> list:
    return [
        model.rollup_date >= since.date(),
        *_rollup_space_filter(model, scope_space_id=scope_space_id),
    ]


def _rollups_have_data(session, *, since: datetime, scope_space_id: str | None) -> bool:
    value = session.execute(
        select(func.count())
        .select_from(UsageDailyRollup)
        .where(*_rollup_date_filters(UsageDailyRollup, since=since, scope_space_id=scope_space_id))
    ).scalar()
    return _int_value(value) > 0


def _event_rollup_key(event: UsageEvent) -> tuple:
    return (
        event.occurred_at.date(),
        _rollup_space_id(event.space_id),
        event.view_key,
        event.category,
        event.feature_key,
        event.action_key,
        event.outcome,
    )


def update_usage_rollups(session, *, events: Iterable[UsageEvent], samples: Iterable[PerformanceSample]) -> None:
    event_totals: dict[tuple, dict[str, object]] = {}
    identity_keys: set[tuple[date, str, str, str]] = set()
    route_identity_keys: set[tuple[date, str, str, str, str]] = set()

    for event in events:
        key = _event_rollup_key(event)
        totals = event_totals.setdefault(
            key,
            {
                "event_count": 0,
                "route_view_count": 0,
                "workflow_action_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "last_occurred_at": event.occurred_at,
            },
        )
        totals["event_count"] = int(totals["event_count"]) + 1
        if event.action_key == "route_view":
            totals["route_view_count"] = int(totals["route_view_count"]) + 1
        if event.category == "workflow":
            totals["workflow_action_count"] = int(totals["workflow_action_count"]) + 1
        if event.outcome == "success":
            totals["success_count"] = int(totals["success_count"]) + 1
        if event.outcome in _FAILURE_OUTCOMES:
            totals["failure_count"] = int(totals["failure_count"]) + 1
        if event.occurred_at > totals["last_occurred_at"]:
            totals["last_occurred_at"] = event.occurred_at

        rollup_date = event.occurred_at.date()
        space_id = _rollup_space_id(event.space_id)
        if event.session_id:
            identity_keys.add((rollup_date, space_id, "session", event.session_id))
            if event.action_key == "route_view":
                route_identity_keys.add((rollup_date, space_id, event.view_key, "session", event.session_id))
        if event.user_id:
            identity_keys.add((rollup_date, space_id, "user", event.user_id))
            if event.action_key == "route_view":
                route_identity_keys.add((rollup_date, space_id, event.view_key, "user", event.user_id))

    for sample in samples:
        rollup_date = sample.occurred_at.date()
        space_id = _rollup_space_id(sample.space_id)
        if sample.session_id:
            identity_keys.add((rollup_date, space_id, "session", sample.session_id))
        if sample.user_id:
            identity_keys.add((rollup_date, space_id, "user", sample.user_id))

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for key, totals in event_totals.items():
        rollup = session.get(UsageDailyRollup, key)
        if rollup is None:
            rollup = UsageDailyRollup(
                rollup_date=key[0],
                space_id=key[1],
                view_key=key[2],
                category=key[3],
                feature_key=key[4],
                action_key=key[5],
                outcome=key[6],
                event_count=0,
                route_view_count=0,
                workflow_action_count=0,
                success_count=0,
                failure_count=0,
                last_occurred_at=totals["last_occurred_at"],
            )
            session.add(rollup)
        rollup.event_count += int(totals["event_count"])
        rollup.route_view_count += int(totals["route_view_count"])
        rollup.workflow_action_count += int(totals["workflow_action_count"])
        rollup.success_count += int(totals["success_count"])
        rollup.failure_count += int(totals["failure_count"])
        if totals["last_occurred_at"] > rollup.last_occurred_at:
            rollup.last_occurred_at = totals["last_occurred_at"]
        rollup.updated_at = now

    for key in identity_keys:
        if session.get(UsageIdentityDailyRollup, key) is None:
            session.add(
                UsageIdentityDailyRollup(
                    rollup_date=key[0],
                    space_id=key[1],
                    token_type=key[2],
                    token_value=key[3],
                    updated_at=now,
                )
            )

    for key in route_identity_keys:
        if session.get(UsageRouteIdentityDailyRollup, key) is None:
            session.add(
                UsageRouteIdentityDailyRollup(
                    rollup_date=key[0],
                    space_id=key[1],
                    view_key=key[2],
                    token_type=key[3],
                    token_value=key[4],
                    updated_at=now,
                )
            )


def _date_bucket_expr(session, value):
    dialect_name = session.get_bind().dialect.name
    if dialect_name == "oracle":
        return func.trunc(value)
    return func.date(value)


def _bucket_to_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value)[:10]).date()


def _int_value(value: object) -> int:
    return int(value or 0)


def _optional_int_value(value: object) -> Optional[int]:
    if value is None:
        return None
    return int(round(float(value)))


def _optional_float_value(value: object) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), 4)


def _sample_load_expr():
    return case(
        (
            PerformanceSample.sample_kind == "route_transition",
            case(
                (
                    PerformanceSample.data_load_ms.is_(None) & PerformanceSample.render_ms.is_(None),
                    None,
                ),
                else_=func.coalesce(PerformanceSample.data_load_ms, 0)
                + func.coalesce(PerformanceSample.render_ms, 0),
            ),
        ),
        else_=PerformanceSample.load_event_ms,
    )


def _event_count(session, *, since: datetime, scope_space_id: str | None, extra_filters: Iterable = ()) -> int:
    filters = [*_base_filters(UsageEvent, since=since, scope_space_id=scope_space_id), *extra_filters]
    value = session.execute(select(func.count()).select_from(UsageEvent).where(*filters)).scalar()
    return _int_value(value)


def _distinct_token_count(session, *, token_name: str, since: datetime, scope_space_id: str | None) -> int:
    event_token = getattr(UsageEvent, token_name)
    sample_token = getattr(PerformanceSample, token_name)
    event_filters = _base_filters(UsageEvent, since=since, scope_space_id=scope_space_id)
    sample_filters = _base_filters(PerformanceSample, since=since, scope_space_id=scope_space_id)
    tokens = union(
        select(event_token.label("token")).where(*event_filters, event_token.isnot(None), event_token != ""),
        select(sample_token.label("token")).where(*sample_filters, sample_token.isnot(None), sample_token != ""),
    ).subquery()
    value = session.execute(select(func.count()).select_from(tokens)).scalar()
    return _int_value(value)


def _daily_distinct_token_counts(
    session,
    *,
    token_name: str,
    since: datetime,
    scope_space_id: str | None,
) -> dict[date, int]:
    event_token = getattr(UsageEvent, token_name)
    sample_token = getattr(PerformanceSample, token_name)
    event_bucket = _date_bucket_expr(session, UsageEvent.occurred_at).label("bucket")
    sample_bucket = _date_bucket_expr(session, PerformanceSample.occurred_at).label("bucket")
    event_filters = _base_filters(UsageEvent, since=since, scope_space_id=scope_space_id)
    sample_filters = _base_filters(PerformanceSample, since=since, scope_space_id=scope_space_id)
    tokens = union(
        select(event_bucket, event_token.label("token")).where(
            *event_filters,
            event_token.isnot(None),
            event_token != "",
        ),
        select(sample_bucket, sample_token.label("token")).where(
            *sample_filters,
            sample_token.isnot(None),
            sample_token != "",
        ),
    ).subquery()
    rows = session.execute(
        select(tokens.c.bucket, func.count().label("total")).group_by(tokens.c.bucket)
    ).all()
    return {_bucket_to_date(row.bucket): _int_value(row.total) for row in rows}


def _daily_event_counts(session, *, since: datetime, scope_space_id: str | None) -> dict[date, dict[str, int]]:
    bucket = _date_bucket_expr(session, UsageEvent.occurred_at).label("bucket")
    filters = _base_filters(UsageEvent, since=since, scope_space_id=scope_space_id)
    route_views_expr = func.coalesce(
        func.sum(case((UsageEvent.action_key == "route_view", 1), else_=0)),
        0,
    )
    workflow_expr = func.coalesce(
        func.sum(case((UsageEvent.category == "workflow", 1), else_=0)),
        0,
    )
    failure_expr = func.coalesce(
        func.sum(case((UsageEvent.outcome.in_(_FAILURE_OUTCOMES), 1), else_=0)),
        0,
    )
    rows = session.execute(
        select(
            bucket,
            route_views_expr.label("route_views"),
            workflow_expr.label("workflow_actions"),
            failure_expr.label("failure_count"),
        )
        .where(*filters)
        .group_by(bucket)
    ).all()
    return {
        _bucket_to_date(row.bucket): {
            "route_views": _int_value(row.route_views),
            "workflow_actions": _int_value(row.workflow_actions),
            "failure_count": _int_value(row.failure_count),
        }
        for row in rows
    }


def _rollup_distinct_token_count(session, *, token_type: str, since: datetime, scope_space_id: str | None) -> int:
    filters = [
        *_rollup_date_filters(UsageIdentityDailyRollup, since=since, scope_space_id=scope_space_id),
        UsageIdentityDailyRollup.token_type == token_type,
    ]
    tokens = (
        select(UsageIdentityDailyRollup.token_value.label("token"))
        .where(*filters)
        .group_by(UsageIdentityDailyRollup.token_value)
        .subquery()
    )
    value = session.execute(select(func.count()).select_from(tokens)).scalar()
    return _int_value(value)


def _rollup_daily_distinct_token_counts(
    session,
    *,
    token_type: str,
    since: datetime,
    scope_space_id: str | None,
) -> dict[date, int]:
    rows = session.execute(
        select(UsageIdentityDailyRollup.rollup_date, func.count().label("total"))
        .where(
            *_rollup_date_filters(UsageIdentityDailyRollup, since=since, scope_space_id=scope_space_id),
            UsageIdentityDailyRollup.token_type == token_type,
        )
        .group_by(UsageIdentityDailyRollup.rollup_date)
    ).all()
    return {_bucket_to_date(row.rollup_date): _int_value(row.total) for row in rows}


def _rollup_daily_event_counts(session, *, since: datetime, scope_space_id: str | None) -> dict[date, dict[str, int]]:
    rows = session.execute(
        select(
            UsageDailyRollup.rollup_date,
            func.coalesce(func.sum(UsageDailyRollup.route_view_count), 0).label("route_views"),
            func.coalesce(func.sum(UsageDailyRollup.workflow_action_count), 0).label("workflow_actions"),
            func.coalesce(func.sum(UsageDailyRollup.failure_count), 0).label("failure_count"),
        )
        .where(*_rollup_date_filters(UsageDailyRollup, since=since, scope_space_id=scope_space_id))
        .group_by(UsageDailyRollup.rollup_date)
    ).all()
    return {
        _bucket_to_date(row.rollup_date): {
            "route_views": _int_value(row.route_views),
            "workflow_actions": _int_value(row.workflow_actions),
            "failure_count": _int_value(row.failure_count),
        }
        for row in rows
    }


def _rollup_event_count(session, *, since: datetime, scope_space_id: str | None, metric_name: str) -> int:
    metric = getattr(UsageDailyRollup, metric_name)
    value = session.execute(
        select(func.coalesce(func.sum(metric), 0)).where(
            *_rollup_date_filters(UsageDailyRollup, since=since, scope_space_id=scope_space_id)
        )
    ).scalar()
    return _int_value(value)


def _ranked_metric_stats_by_group(
    session,
    *,
    group_expr,
    metric_expr,
    filters: Iterable,
) -> dict[object, dict[str, Optional[int]]]:
    base = (
        select(group_expr.label("group_key"), metric_expr.label("metric_value"))
        .where(*filters, metric_expr.isnot(None))
        .subquery()
    )
    ranked = select(
        base.c.group_key,
        base.c.metric_value,
        func.row_number()
        .over(partition_by=base.c.group_key, order_by=base.c.metric_value)
        .label("rn"),
        func.count().over(partition_by=base.c.group_key).label("cnt"),
    ).subquery()

    median_low_rank = func.floor((ranked.c.cnt + 1) / 2)
    median_high_rank = func.floor((ranked.c.cnt + 2) / 2)
    median_condition = or_(
        ranked.c.rn == median_low_rank,
        ranked.c.rn == median_high_rank,
    )
    p95_rank = func.ceil((ranked.c.cnt * 95.0) / 100.0)

    rows = session.execute(
        select(
            ranked.c.group_key,
            func.round(
                func.avg(case((median_condition, ranked.c.metric_value), else_=None))
            ).label("median_value"),
            func.round(
                func.max(case((ranked.c.rn == p95_rank, ranked.c.metric_value), else_=None))
            ).label("p95_value"),
        )
        .group_by(ranked.c.group_key)
    ).all()
    return {
        row.group_key: {
            "median": _optional_int_value(row.median_value),
            "p95": _optional_int_value(row.p95_value),
        }
        for row in rows
    }


def _load_stats_by_sample_kind(session, *, filters: Iterable, load_expr) -> dict[str, dict[str, Optional[int]]]:
    return {
        str(kind): stats
        for kind, stats in _ranked_metric_stats_by_group(
            session,
            group_expr=PerformanceSample.sample_kind,
            metric_expr=load_expr,
            filters=filters,
        ).items()
    }


def _load_summary_stats(session, *, filters: Iterable, load_expr) -> dict[str, dict]:
    return {
        "overall": _ranked_metric_stats_by_group(
            session,
            group_expr=literal("all"),
            metric_expr=load_expr,
            filters=filters,
        ).get("all", {}),
        "by_kind": _load_stats_by_sample_kind(session, filters=filters, load_expr=load_expr),
    }


def build_summary_payload(
    session,
    *,
    days: int,
    all_spaces: bool,
    scope_space_id: str | None,
    load_summary_stats: dict[str, dict] | None = None,
) -> dict:
    since = analytics_window_start(days)
    use_rollups = _rollups_have_data(session, since=since, scope_space_id=scope_space_id)
    sample_filters = _base_filters(PerformanceSample, since=since, scope_space_id=scope_space_id)
    load_expr = _sample_load_expr()
    load_summary_stats = load_summary_stats or _load_summary_stats(
        session,
        filters=sample_filters,
        load_expr=load_expr,
    )
    overall_load_stats = load_summary_stats.get("overall", {})
    load_stats_by_kind = load_summary_stats.get("by_kind", {})
    navigation_load_stats = load_stats_by_kind.get("navigation", {})
    route_transition_load_stats = load_stats_by_kind.get("route_transition", {})
    raw_daily_load_stats = _ranked_metric_stats_by_group(
        session,
        group_expr=_date_bucket_expr(session, PerformanceSample.occurred_at),
        metric_expr=load_expr,
        filters=sample_filters,
    )
    daily_load_stats = {
        _bucket_to_date(bucket): stats
        for bucket, stats in raw_daily_load_stats.items()
    }
    if use_rollups:
        daily_event_counts = _rollup_daily_event_counts(session, since=since, scope_space_id=scope_space_id)
        daily_session_counts = _rollup_daily_distinct_token_counts(
            session,
            token_type="session",
            since=since,
            scope_space_id=scope_space_id,
        )
        daily_user_counts = _rollup_daily_distinct_token_counts(
            session,
            token_type="user",
            since=since,
            scope_space_id=scope_space_id,
        )
        sessions = _rollup_distinct_token_count(
            session,
            token_type="session",
            since=since,
            scope_space_id=scope_space_id,
        )
        active_users = _rollup_distinct_token_count(
            session,
            token_type="user",
            since=since,
            scope_space_id=scope_space_id,
        )
        route_views = _rollup_event_count(
            session,
            since=since,
            scope_space_id=scope_space_id,
            metric_name="route_view_count",
        )
        workflow_actions = _rollup_event_count(
            session,
            since=since,
            scope_space_id=scope_space_id,
            metric_name="workflow_action_count",
        )
        failure_count = _rollup_event_count(
            session,
            since=since,
            scope_space_id=scope_space_id,
            metric_name="failure_count",
        )
    else:
        daily_event_counts = _daily_event_counts(session, since=since, scope_space_id=scope_space_id)
        daily_session_counts = _daily_distinct_token_counts(
            session,
            token_name="session_id",
            since=since,
            scope_space_id=scope_space_id,
        )
        daily_user_counts = _daily_distinct_token_counts(
            session,
            token_name="user_id",
            since=since,
            scope_space_id=scope_space_id,
        )
        sessions = _distinct_token_count(
            session,
            token_name="session_id",
            since=since,
            scope_space_id=scope_space_id,
        )
        active_users = _distinct_token_count(
            session,
            token_name="user_id",
            since=since,
            scope_space_id=scope_space_id,
        )
        route_views = _event_count(
            session,
            since=since,
            scope_space_id=scope_space_id,
            extra_filters=(UsageEvent.action_key == "route_view",),
        )
        workflow_actions = _event_count(
            session,
            since=since,
            scope_space_id=scope_space_id,
            extra_filters=(UsageEvent.category == "workflow",),
        )
        failure_count = _event_count(
            session,
            since=since,
            scope_space_id=scope_space_id,
            extra_filters=(UsageEvent.outcome.in_(_FAILURE_OUTCOMES),),
        )

    window_days = {(since + timedelta(days=offset)).date() for offset in range(days)}
    daily_dates = sorted(
        window_days
        | set(daily_event_counts)
        | set(daily_session_counts)
        | set(daily_user_counts)
        | set(daily_load_stats)
    )
    daily = []
    for bucket_date in daily_dates:
        event_counts = daily_event_counts.get(bucket_date, {})
        load_stats = daily_load_stats.get(bucket_date, {})
        daily.append(
            {
                "date": bucket_date.isoformat(),
                "sessions": daily_session_counts.get(bucket_date, 0),
                "active_users": daily_user_counts.get(bucket_date, 0),
                "route_views": event_counts.get("route_views", 0),
                "workflow_actions": event_counts.get("workflow_actions", 0),
                "failure_count": event_counts.get("failure_count", 0),
                "median_load_ms": load_stats.get("median"),
                "p95_load_ms": load_stats.get("p95"),
            }
        )

    return {
        **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
        "summary": {
            "sessions": sessions,
            "active_users": active_users,
            "route_views": route_views,
            "workflow_actions": workflow_actions,
            "failure_count": failure_count,
            "median_load_ms": overall_load_stats.get("median"),
            "p95_load_ms": overall_load_stats.get("p95"),
            "navigation_median_load_ms": navigation_load_stats.get("median"),
            "navigation_p95_load_ms": navigation_load_stats.get("p95"),
            "route_transition_median_load_ms": route_transition_load_stats.get("median"),
            "route_transition_p95_load_ms": route_transition_load_stats.get("p95"),
        },
        "daily": daily,
    }


def build_route_stats_payload(session, *, days: int, all_spaces: bool, scope_space_id: str | None) -> dict:
    since = analytics_window_start(days)
    if _rollups_have_data(session, since=since, scope_space_id=scope_space_id):
        filters = _rollup_date_filters(UsageDailyRollup, since=since, scope_space_id=scope_space_id)
        route_views_expr = func.coalesce(func.sum(UsageDailyRollup.route_view_count), 0)
        route_failure_expr = func.coalesce(func.sum(UsageDailyRollup.failure_count), 0)
        top_route_rows = session.execute(
            select(
                UsageDailyRollup.view_key.label("view_key"),
                route_views_expr.label("route_views"),
                route_failure_expr.label("failure_count"),
            )
            .where(*filters)
            .group_by(UsageDailyRollup.view_key)
            .having((route_views_expr > 0) | (route_failure_expr > 0))
            .order_by(route_views_expr.desc(), UsageDailyRollup.view_key.asc())
            .limit(10)
        ).all()

        top_view_keys = [row.view_key for row in top_route_rows]
        route_identity_counts: dict[tuple[str, str], int] = {}
        if top_view_keys:
            distinct_route_tokens = (
                select(
                    UsageRouteIdentityDailyRollup.view_key.label("view_key"),
                    UsageRouteIdentityDailyRollup.token_type.label("token_type"),
                    UsageRouteIdentityDailyRollup.token_value.label("token_value"),
                )
                .where(
                    *_rollup_date_filters(
                        UsageRouteIdentityDailyRollup,
                        since=since,
                        scope_space_id=scope_space_id,
                    ),
                    UsageRouteIdentityDailyRollup.view_key.in_(top_view_keys),
                )
                .group_by(
                    UsageRouteIdentityDailyRollup.view_key,
                    UsageRouteIdentityDailyRollup.token_type,
                    UsageRouteIdentityDailyRollup.token_value,
                )
                .subquery()
            )
            identity_rows = session.execute(
                select(
                    distinct_route_tokens.c.view_key,
                    distinct_route_tokens.c.token_type,
                    func.count().label("total"),
                )
                .group_by(distinct_route_tokens.c.view_key, distinct_route_tokens.c.token_type)
            ).all()
            route_identity_counts = {
                (row.view_key, row.token_type): _int_value(row.total)
                for row in identity_rows
            }

        top_routes = [
            {
                "view_key": row.view_key,
                "route_views": _int_value(row.route_views),
                "unique_sessions": route_identity_counts.get((row.view_key, "session"), 0),
                "active_users": route_identity_counts.get((row.view_key, "user"), 0),
                "failure_count": _int_value(row.failure_count),
            }
            for row in top_route_rows
        ]

        workflow_total_expr = func.coalesce(func.sum(UsageDailyRollup.workflow_action_count), 0)
        workflow_success_expr = func.coalesce(func.sum(UsageDailyRollup.success_count), 0)
        workflow_failure_expr = func.coalesce(func.sum(UsageDailyRollup.failure_count), 0)
        workflow_rows = session.execute(
            select(
                UsageDailyRollup.feature_key.label("feature_key"),
                UsageDailyRollup.action_key.label("action_key"),
                workflow_total_expr.label("total"),
                workflow_success_expr.label("success_count"),
                workflow_failure_expr.label("failure_count"),
            )
            .where(*filters, UsageDailyRollup.category == "workflow")
            .group_by(UsageDailyRollup.feature_key, UsageDailyRollup.action_key)
            .order_by(workflow_total_expr.desc(), UsageDailyRollup.feature_key.asc(), UsageDailyRollup.action_key.asc())
            .limit(10)
        ).all()
        top_workflows = [
            {
                "feature_key": row.feature_key,
                "action_key": row.action_key,
                "total": _int_value(row.total),
                "success_count": _int_value(row.success_count),
                "failure_count": _int_value(row.failure_count),
            }
            for row in workflow_rows
        ]

        failure_count_expr = func.coalesce(func.sum(UsageDailyRollup.failure_count), 0)
        last_seen_expr = func.max(UsageDailyRollup.last_occurred_at)
        failure_rows = session.execute(
            select(
                UsageDailyRollup.view_key.label("view_key"),
                UsageDailyRollup.feature_key.label("feature_key"),
                UsageDailyRollup.action_key.label("action_key"),
                failure_count_expr.label("failure_count"),
                last_seen_expr.label("last_occurred_at"),
            )
            .where(*filters, UsageDailyRollup.failure_count > 0)
            .group_by(UsageDailyRollup.view_key, UsageDailyRollup.feature_key, UsageDailyRollup.action_key)
            .order_by(last_seen_expr.desc(), failure_count_expr.desc())
            .limit(10)
        ).all()
        recent_failures = [
            {
                "view_key": row.view_key,
                "feature_key": row.feature_key,
                "action_key": row.action_key,
                "failure_count": _int_value(row.failure_count),
                "last_occurred_at": row.last_occurred_at,
            }
            for row in failure_rows
        ]

        return {
            **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
            "top_routes": top_routes,
            "top_workflows": top_workflows,
            "recent_failures": recent_failures[:10],
        }

    filters = _base_filters(UsageEvent, since=since, scope_space_id=scope_space_id)
    route_views_expr = func.coalesce(
        func.sum(case((UsageEvent.action_key == "route_view", 1), else_=0)),
        0,
    )
    route_failure_expr = func.coalesce(
        func.sum(case((UsageEvent.outcome.in_(_FAILURE_OUTCOMES), 1), else_=0)),
        0,
    )
    top_route_rows = session.execute(
        select(
            UsageEvent.view_key.label("view_key"),
            route_views_expr.label("route_views"),
            func.count(
                func.distinct(
                    case((UsageEvent.action_key == "route_view", UsageEvent.session_id), else_=None)
                )
            ).label("unique_sessions"),
            func.count(
                func.distinct(
                    case((UsageEvent.action_key == "route_view", UsageEvent.user_id), else_=None)
                )
            ).label("active_users"),
            route_failure_expr.label("failure_count"),
        )
        .where(
            *filters,
            or_(
                UsageEvent.action_key == "route_view",
                UsageEvent.outcome.in_(_FAILURE_OUTCOMES),
            ),
        )
        .group_by(UsageEvent.view_key)
        .order_by(route_views_expr.desc(), UsageEvent.view_key.asc())
        .limit(10)
    ).all()
    top_routes = [
        {
            "view_key": row.view_key,
            "route_views": _int_value(row.route_views),
            "unique_sessions": _int_value(row.unique_sessions),
            "active_users": _int_value(row.active_users),
            "failure_count": _int_value(row.failure_count),
        }
        for row in top_route_rows
    ]

    workflow_total_expr = func.count()
    workflow_success_expr = func.coalesce(
        func.sum(case((UsageEvent.outcome == "success", 1), else_=0)),
        0,
    )
    workflow_failure_expr = func.coalesce(
        func.sum(case((UsageEvent.outcome.in_(_FAILURE_OUTCOMES), 1), else_=0)),
        0,
    )
    workflow_rows = session.execute(
        select(
            UsageEvent.feature_key.label("feature_key"),
            UsageEvent.action_key.label("action_key"),
            workflow_total_expr.label("total"),
            workflow_success_expr.label("success_count"),
            workflow_failure_expr.label("failure_count"),
        )
        .where(*filters, UsageEvent.category == "workflow")
        .group_by(UsageEvent.feature_key, UsageEvent.action_key)
        .order_by(workflow_total_expr.desc(), UsageEvent.feature_key.asc(), UsageEvent.action_key.asc())
        .limit(10)
    ).all()
    top_workflows = [
        {
            "feature_key": row.feature_key,
            "action_key": row.action_key,
            "total": _int_value(row.total),
            "success_count": _int_value(row.success_count),
            "failure_count": _int_value(row.failure_count),
        }
        for row in workflow_rows
    ]

    failure_count_expr = func.count()
    last_seen_expr = func.max(UsageEvent.occurred_at)
    failure_rows = session.execute(
        select(
            UsageEvent.view_key.label("view_key"),
            UsageEvent.feature_key.label("feature_key"),
            UsageEvent.action_key.label("action_key"),
            failure_count_expr.label("failure_count"),
            last_seen_expr.label("last_occurred_at"),
        )
        .where(*filters, UsageEvent.outcome.in_(_FAILURE_OUTCOMES))
        .group_by(UsageEvent.view_key, UsageEvent.feature_key, UsageEvent.action_key)
        .order_by(last_seen_expr.desc(), failure_count_expr.desc())
        .limit(10)
    ).all()
    recent_failures = [
        {
            "view_key": row.view_key,
            "feature_key": row.feature_key,
            "action_key": row.action_key,
            "failure_count": _int_value(row.failure_count),
            "last_occurred_at": row.last_occurred_at,
        }
        for row in failure_rows
    ]

    return {
        **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
        "top_routes": top_routes,
        "top_workflows": top_workflows,
        "recent_failures": recent_failures[:10],
    }


def build_performance_stats_payload(
    session,
    *,
    days: int,
    all_spaces: bool,
    scope_space_id: str | None,
    load_summary_stats: dict[str, dict] | None = None,
) -> dict:
    since = analytics_window_start(days)
    filters = _base_filters(PerformanceSample, since=since, scope_space_id=scope_space_id)
    kind_rows = session.execute(
        select(PerformanceSample.sample_kind, func.count().label("total"))
        .where(*filters)
        .group_by(PerformanceSample.sample_kind)
    ).all()
    kind_counts = {row.sample_kind: _int_value(row.total) for row in kind_rows}
    load_expr = _sample_load_expr()
    load_summary_stats = load_summary_stats or _load_summary_stats(
        session,
        filters=filters,
        load_expr=load_expr,
    )
    total_load_stats = load_summary_stats.get("overall", {})
    load_stats_by_kind = load_summary_stats.get("by_kind", {})
    navigation_load_stats = load_stats_by_kind.get("navigation", {})
    route_transition_load_stats = load_stats_by_kind.get("route_transition", {})
    route_rows = session.execute(
        select(
            PerformanceSample.view_key.label("view_key"),
            func.count(load_expr).label("sample_count"),
            func.avg(PerformanceSample.cls_score).label("avg_cls_score"),
            func.coalesce(func.sum(func.coalesce(PerformanceSample.long_task_count, 0)), 0).label("long_task_count"),
        )
        .where(*filters)
        .group_by(PerformanceSample.view_key)
        .having(func.count(load_expr) > 0)
    ).all()
    route_groups = {
        row.view_key: {
            "view_key": row.view_key,
            "sample_count": _int_value(row.sample_count),
            "avg_cls_score": _optional_float_value(row.avg_cls_score),
            "long_task_count": _int_value(row.long_task_count),
        }
        for row in route_rows
    }

    load_stats_by_route = _ranked_metric_stats_by_group(
        session,
        group_expr=PerformanceSample.view_key,
        metric_expr=load_expr,
        filters=filters,
    )
    data_stats_by_route = _ranked_metric_stats_by_group(
        session,
        group_expr=PerformanceSample.view_key,
        metric_expr=PerformanceSample.data_load_ms,
        filters=filters,
    )
    render_stats_by_route = _ranked_metric_stats_by_group(
        session,
        group_expr=PerformanceSample.view_key,
        metric_expr=PerformanceSample.render_ms,
        filters=filters,
    )
    fcp_stats_by_route = _ranked_metric_stats_by_group(
        session,
        group_expr=PerformanceSample.view_key,
        metric_expr=PerformanceSample.first_contentful_paint_ms,
        filters=filters,
    )
    lcp_stats_by_route = _ranked_metric_stats_by_group(
        session,
        group_expr=PerformanceSample.view_key,
        metric_expr=PerformanceSample.largest_contentful_paint_ms,
        filters=filters,
    )

    routes = []
    for view_key, route in route_groups.items():
        load_stats = load_stats_by_route.get(view_key, {})
        data_stats = data_stats_by_route.get(view_key, {})
        render_stats = render_stats_by_route.get(view_key, {})
        fcp_stats = fcp_stats_by_route.get(view_key, {})
        lcp_stats = lcp_stats_by_route.get(view_key, {})
        routes.append({
            **route,
            "median_load_ms": load_stats.get("median"),
            "p95_load_ms": load_stats.get("p95"),
            "median_data_load_ms": data_stats.get("median"),
            "p95_data_load_ms": data_stats.get("p95"),
            "median_render_ms": render_stats.get("median"),
            "p95_render_ms": render_stats.get("p95"),
            "median_first_contentful_paint_ms": fcp_stats.get("median"),
            "p95_largest_contentful_paint_ms": lcp_stats.get("p95"),
        })
    routes.sort(key=lambda row: (-(row["p95_load_ms"] or 0), row["view_key"]))

    return {
        **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
        "summary": {
            "navigation_samples": kind_counts.get("navigation", 0),
            "route_transition_samples": kind_counts.get("route_transition", 0),
            "median_load_ms": total_load_stats.get("median"),
            "p95_load_ms": total_load_stats.get("p95"),
            "navigation_median_load_ms": navigation_load_stats.get("median"),
            "navigation_p95_load_ms": navigation_load_stats.get("p95"),
            "route_transition_median_load_ms": route_transition_load_stats.get("median"),
            "route_transition_p95_load_ms": route_transition_load_stats.get("p95"),
        },
        "routes": routes[:10],
    }


def build_dashboard_payload(session, *, days: int, all_spaces: bool, scope_space_id: str | None) -> dict:
    since = analytics_window_start(days)
    sample_filters = _base_filters(PerformanceSample, since=since, scope_space_id=scope_space_id)
    load_expr = _sample_load_expr()
    load_summary_stats = _load_summary_stats(session, filters=sample_filters, load_expr=load_expr)
    return {
        "summary": build_summary_payload(
            session,
            days=days,
            all_spaces=all_spaces,
            scope_space_id=scope_space_id,
            load_summary_stats=load_summary_stats,
        ),
        "routes": build_route_stats_payload(
            session,
            days=days,
            all_spaces=all_spaces,
            scope_space_id=scope_space_id,
        ),
        "performance": build_performance_stats_payload(
            session,
            days=days,
            all_spaces=all_spaces,
            scope_space_id=scope_space_id,
            load_summary_stats=load_summary_stats,
        ),
    }


__all__ = [
    "ALLOWED_ACTION_KEYS",
    "ALLOWED_DETAIL_KEYS",
    "ALLOWED_EVENT_CATEGORIES",
    "ALLOWED_FEATURE_KEYS",
    "ALLOWED_OUTCOMES",
    "ALLOWED_SAMPLE_KINDS",
    "analytics_scope_read",
    "analytics_window_days_query",
    "build_dashboard_payload",
    "build_performance_stats_payload",
    "build_route_stats_payload",
    "build_summary_payload",
    "enforce_batch_limits",
    "ensure_usage_analytics_available",
    "normalize_timestamp",
    "sanitize_details",
    "scope_space_id_for_request",
    "update_usage_rollups",
    "usage_analytics_enabled",
    "validate_performance_sample_payload",
    "validate_requested_analytics_space",
    "validate_usage_event_payload",
    "validate_window_days",
]
