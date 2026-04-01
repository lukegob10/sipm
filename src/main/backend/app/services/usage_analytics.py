from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import median
from typing import Iterable, Optional

from fastapi import Query
from sqlalchemy import inspect

from ..db.table_names import physical_table_name
from ..models import PerformanceSample, UsageEvent
from ..security import security_http_exception


_ALLOWED_WINDOW_DAYS = {7, 30, 90}
_MAX_BATCH_SIZE = 100
_MAX_DETAILS_BYTES = 1024
_MAX_DETAIL_VALUE_LENGTH = 160
_MAX_DURATION_MS = 24 * 60 * 60 * 1000

ALLOWED_EVENT_CATEGORIES = {"lifecycle", "navigation", "workflow", "operations"}
ALLOWED_FEATURE_KEYS = {
    "analytics",
    "app",
    "csv",
    "navigation",
    "planning",
    "projects",
    "spaces",
    "subcomponents",
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
    inspector = inspect(bind)
    required_tables = [
        physical_table_name("usage_events"),
        physical_table_name("performance_samples"),
    ]
    for table_name in required_tables:
        if not inspector.has_table(table_name):
            raise security_http_exception(
                status_code=503,
                code="USAGE_ANALYTICS_SCHEMA_MISSING",
                message="Usage analytics schema is not available",
            )


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


def _query_events(session, *, since: datetime, scope_space_id: str | None) -> list[UsageEvent]:
    query = session.query(UsageEvent).filter(UsageEvent.occurred_at >= since)
    if scope_space_id:
        query = query.filter(UsageEvent.space_id == scope_space_id)
    return query.order_by(UsageEvent.occurred_at.asc()).all()


def _query_samples(session, *, since: datetime, scope_space_id: str | None) -> list[PerformanceSample]:
    query = session.query(PerformanceSample).filter(PerformanceSample.occurred_at >= since)
    if scope_space_id:
        query = query.filter(PerformanceSample.space_id == scope_space_id)
    return query.order_by(PerformanceSample.occurred_at.asc()).all()


def _percentile(values: Iterable[int | float], ratio: float) -> Optional[int]:
    ordered = sorted(float(value) for value in values if value is not None)
    if not ordered:
        return None
    if len(ordered) == 1:
        return int(round(ordered[0]))
    idx = max(int(math.ceil(len(ordered) * ratio)) - 1, 0)
    return int(round(ordered[min(idx, len(ordered) - 1)]))


def _median(values: Iterable[int | float]) -> Optional[int]:
    ordered = [float(value) for value in values if value is not None]
    if not ordered:
        return None
    return int(round(median(ordered)))


def _mean(values: Iterable[int | float]) -> Optional[float]:
    ordered = [float(value) for value in values if value is not None]
    if not ordered:
        return None
    return round(sum(ordered) / len(ordered), 4)


def _event_is_failure(event: UsageEvent) -> bool:
    return str(event.outcome or "").lower() in {"failure", "timeout", "server_error"}


def _sample_load_value(sample: PerformanceSample) -> Optional[int]:
    if sample.sample_kind == "route_transition":
        if sample.data_load_ms is None and sample.render_ms is None:
            return None
        return int(sample.data_load_ms or 0) + int(sample.render_ms or 0)
    return sample.load_event_ms


def _date_bucket(value: datetime) -> date:
    return value.date()


def build_summary_payload(session, *, days: int, all_spaces: bool, scope_space_id: str | None) -> dict:
    since = analytics_window_start(days)
    events = _query_events(session, since=since, scope_space_id=scope_space_id)
    samples = _query_samples(session, since=since, scope_space_id=scope_space_id)

    unique_sessions = {
        str(token).strip()
        for token in [*(event.session_id for event in events), *(sample.session_id for sample in samples)]
        if str(token or "").strip()
    }
    unique_users = {
        str(token).strip()
        for token in [*(event.user_id for event in events), *(sample.user_id for sample in samples)]
        if str(token or "").strip()
    }
    route_views = [event for event in events if event.action_key == "route_view"]
    workflow_events = [event for event in events if event.category == "workflow"]
    failure_events = [event for event in events if _event_is_failure(event)]
    load_values = [_sample_load_value(sample) for sample in samples]

    by_day: dict[date, dict[str, object]] = {}
    for offset in range(days):
        bucket = (since + timedelta(days=offset)).date()
        by_day[bucket] = {
            "sessions": set(),
            "active_users": set(),
            "route_views": 0,
            "workflow_actions": 0,
            "failure_count": 0,
            "load_values": [],
        }

    for event in events:
        bucket = by_day.setdefault(_date_bucket(event.occurred_at), {
            "sessions": set(),
            "active_users": set(),
            "route_views": 0,
            "workflow_actions": 0,
            "failure_count": 0,
            "load_values": [],
        })
        if event.session_id:
            bucket["sessions"].add(event.session_id)
        if event.user_id:
            bucket["active_users"].add(event.user_id)
        if event.action_key == "route_view":
            bucket["route_views"] += 1
        if event.category == "workflow":
            bucket["workflow_actions"] += 1
        if _event_is_failure(event):
            bucket["failure_count"] += 1

    for sample in samples:
        bucket = by_day.setdefault(_date_bucket(sample.occurred_at), {
            "sessions": set(),
            "active_users": set(),
            "route_views": 0,
            "workflow_actions": 0,
            "failure_count": 0,
            "load_values": [],
        })
        if sample.session_id:
            bucket["sessions"].add(sample.session_id)
        if sample.user_id:
            bucket["active_users"].add(sample.user_id)
        load_value = _sample_load_value(sample)
        if load_value is not None:
            bucket["load_values"].append(load_value)

    daily = []
    for bucket_date in sorted(by_day):
        bucket = by_day[bucket_date]
        daily.append({
            "date": bucket_date.isoformat(),
            "sessions": len(bucket["sessions"]),
            "active_users": len(bucket["active_users"]),
            "route_views": int(bucket["route_views"]),
            "workflow_actions": int(bucket["workflow_actions"]),
            "failure_count": int(bucket["failure_count"]),
            "median_load_ms": _median(bucket["load_values"]),
            "p95_load_ms": _percentile(bucket["load_values"], 0.95),
        })

    return {
        **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
        "summary": {
            "sessions": len(unique_sessions),
            "active_users": len(unique_users),
            "route_views": len(route_views),
            "workflow_actions": len(workflow_events),
            "failure_count": len(failure_events),
            "median_load_ms": _median(load_values),
            "p95_load_ms": _percentile(load_values, 0.95),
        },
        "daily": daily,
    }


def build_route_stats_payload(session, *, days: int, all_spaces: bool, scope_space_id: str | None) -> dict:
    since = analytics_window_start(days)
    events = _query_events(session, since=since, scope_space_id=scope_space_id)

    route_groups: dict[str, dict[str, object]] = defaultdict(lambda: {
        "route_views": 0,
        "sessions": set(),
        "users": set(),
        "failures": 0,
    })
    workflow_groups: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: {
        "total": 0,
        "success_count": 0,
        "failure_count": 0,
    })
    failure_groups: dict[tuple[str, str, str], dict[str, object]] = defaultdict(lambda: {
        "failure_count": 0,
        "last_occurred_at": None,
    })

    for event in events:
        if event.action_key == "route_view":
            route_group = route_groups[event.view_key]
            route_group["route_views"] += 1
            if event.session_id:
                route_group["sessions"].add(event.session_id)
            if event.user_id:
                route_group["users"].add(event.user_id)
        if event.category == "workflow":
            workflow_group = workflow_groups[(event.feature_key, event.action_key)]
            workflow_group["total"] += 1
            if _event_is_failure(event):
                workflow_group["failure_count"] += 1
            elif event.outcome == "success":
                workflow_group["success_count"] += 1
        if _event_is_failure(event):
            route_groups[event.view_key]["failures"] += 1
            failure_group = failure_groups[(event.view_key, event.feature_key, event.action_key)]
            failure_group["failure_count"] += 1
            last_seen = failure_group["last_occurred_at"]
            if last_seen is None or event.occurred_at > last_seen:
                failure_group["last_occurred_at"] = event.occurred_at

    top_routes = sorted(
        (
            {
                "view_key": view_key,
                "route_views": int(values["route_views"]),
                "unique_sessions": len(values["sessions"]),
                "active_users": len(values["users"]),
                "failure_count": int(values["failures"]),
            }
            for view_key, values in route_groups.items()
        ),
        key=lambda row: (-row["route_views"], row["view_key"]),
    )[:10]

    top_workflows = sorted(
        (
            {
                "feature_key": feature_key,
                "action_key": action_key,
                "total": values["total"],
                "success_count": values["success_count"],
                "failure_count": values["failure_count"],
            }
            for (feature_key, action_key), values in workflow_groups.items()
        ),
        key=lambda row: (-row["total"], row["feature_key"], row["action_key"]),
    )[:10]

    recent_failures = sorted(
        (
            {
                "view_key": view_key,
                "feature_key": feature_key,
                "action_key": action_key,
                "failure_count": values["failure_count"],
                "last_occurred_at": values["last_occurred_at"],
            }
            for (view_key, feature_key, action_key), values in failure_groups.items()
            if values["last_occurred_at"] is not None
        ),
        key=lambda row: (-row["failure_count"], row["last_occurred_at"]),
        reverse=False,
    )
    recent_failures.sort(key=lambda row: (row["last_occurred_at"], row["failure_count"]), reverse=True)

    return {
        **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
        "top_routes": top_routes,
        "top_workflows": top_workflows,
        "recent_failures": recent_failures[:10],
    }


def build_performance_stats_payload(session, *, days: int, all_spaces: bool, scope_space_id: str | None) -> dict:
    since = analytics_window_start(days)
    samples = _query_samples(session, since=since, scope_space_id=scope_space_id)

    route_groups: dict[str, list[PerformanceSample]] = defaultdict(list)
    navigation_count = 0
    route_transition_count = 0
    total_load_values = []
    for sample in samples:
        route_groups[sample.view_key].append(sample)
        if sample.sample_kind == "navigation":
            navigation_count += 1
        if sample.sample_kind == "route_transition":
            route_transition_count += 1
        load_value = _sample_load_value(sample)
        if load_value is not None:
            total_load_values.append(load_value)

    routes = []
    for view_key, route_samples in route_groups.items():
        load_values = [_sample_load_value(sample) for sample in route_samples]
        routes.append({
            "view_key": view_key,
            "sample_count": len(route_samples),
            "median_load_ms": _median(load_values),
            "p95_load_ms": _percentile(load_values, 0.95),
            "median_data_load_ms": _median(sample.data_load_ms for sample in route_samples),
            "p95_data_load_ms": _percentile((sample.data_load_ms for sample in route_samples), 0.95),
            "median_render_ms": _median(sample.render_ms for sample in route_samples),
            "p95_render_ms": _percentile((sample.render_ms for sample in route_samples), 0.95),
            "median_first_contentful_paint_ms": _median(sample.first_contentful_paint_ms for sample in route_samples),
            "p95_largest_contentful_paint_ms": _percentile((sample.largest_contentful_paint_ms for sample in route_samples), 0.95),
            "avg_cls_score": _mean(sample.cls_score for sample in route_samples),
            "long_task_count": sum(int(sample.long_task_count or 0) for sample in route_samples),
        })
    routes.sort(key=lambda row: (-(row["p95_load_ms"] or 0), row["view_key"]))

    return {
        **analytics_scope_read(days=days, all_spaces=all_spaces, scope_space_id=scope_space_id),
        "summary": {
            "navigation_samples": navigation_count,
            "route_transition_samples": route_transition_count,
            "median_load_ms": _median(total_load_values),
            "p95_load_ms": _percentile(total_load_values, 0.95),
        },
        "routes": routes[:10],
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
    "build_performance_stats_payload",
    "build_route_stats_payload",
    "build_summary_payload",
    "enforce_batch_limits",
    "ensure_usage_analytics_available",
    "normalize_timestamp",
    "sanitize_details",
    "scope_space_id_for_request",
    "usage_analytics_enabled",
    "validate_performance_sample_payload",
    "validate_usage_event_payload",
    "validate_window_days",
]
