from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import current_space as current_space_dep
from ..deps import current_user as current_user_dep
from ..deps import get_db, require_global_admin
from ..models import PerformanceSample, UsageEvent, User
from ..schemas import (
    AnalyticsPerformanceStatsRead,
    AnalyticsDashboardRead,
    AnalyticsRouteStatsRead,
    AnalyticsSummaryRead,
    TelemetryBatchIn,
    TelemetryIngestResultRead,
)
from ..services.spaces import SpaceContext
from ..services.usage_analytics import (
    build_dashboard_payload,
    build_performance_stats_payload,
    build_route_stats_payload,
    build_summary_payload,
    enforce_batch_limits,
    ensure_usage_analytics_available,
    normalize_timestamp,
    sanitize_details,
    scope_space_id_for_request,
    update_usage_rollups,
    validate_performance_sample_payload,
    validate_requested_analytics_space,
    validate_usage_event_payload,
    validate_window_days,
)


router = APIRouter(prefix="/analytics")


@router.post("/ingest", response_model=TelemetryIngestResultRead)
def ingest_usage_analytics(
    payload: TelemetryBatchIn,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    ensure_usage_analytics_available(session)
    enforce_batch_limits(len(payload.events), len(payload.performance_samples))

    received_at = datetime.now(timezone.utc).replace(tzinfo=None)
    events_to_insert: list[UsageEvent] = []
    samples_to_insert: list[PerformanceSample] = []

    for event in payload.events:
        validate_usage_event_payload(event)
        events_to_insert.append(
            UsageEvent(
                occurred_at=normalize_timestamp(event.occurred_at),
                received_at=received_at,
                session_id=event.session_id,
                user_id=current_user.user_id,
                space_id=space_ctx.space_id,
                view_key=event.view_key,
                category=event.category,
                feature_key=event.feature_key,
                action_key=event.action_key,
                outcome=event.outcome,
                duration_ms=event.duration_ms,
                status_code=event.status_code,
                details_json=sanitize_details(event.details),
            )
        )

    for sample in payload.performance_samples:
        validate_performance_sample_payload(sample)
        samples_to_insert.append(
            PerformanceSample(
                occurred_at=normalize_timestamp(sample.occurred_at),
                received_at=received_at,
                session_id=sample.session_id,
                user_id=current_user.user_id,
                space_id=space_ctx.space_id,
                view_key=sample.view_key,
                sample_kind=sample.sample_kind,
                navigation_type=sample.navigation_type,
                data_load_ms=sample.data_load_ms,
                render_ms=sample.render_ms,
                ttfb_ms=sample.ttfb_ms,
                dom_interactive_ms=sample.dom_interactive_ms,
                dom_content_loaded_ms=sample.dom_content_loaded_ms,
                load_event_ms=sample.load_event_ms,
                first_paint_ms=sample.first_paint_ms,
                first_contentful_paint_ms=sample.first_contentful_paint_ms,
                largest_contentful_paint_ms=sample.largest_contentful_paint_ms,
                cls_score=sample.cls_score,
                long_task_count=sample.long_task_count,
                long_task_total_ms=sample.long_task_total_ms,
            )
        )

    if events_to_insert:
        session.add_all(events_to_insert)
    if samples_to_insert:
        session.add_all(samples_to_insert)
    update_usage_rollups(session, events=events_to_insert, samples=samples_to_insert)
    session.commit()

    return TelemetryIngestResultRead(
        status="ok",
        events_ingested=len(events_to_insert),
        performance_samples_ingested=len(samples_to_insert),
    )


@router.get("/summary", response_model=AnalyticsSummaryRead)
def get_usage_analytics_summary(
    days: int = 30,
    all_spaces: bool = False,
    space_id: str | None = None,
    session: Session = Depends(get_db),
    _global_admin: User = Depends(require_global_admin),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    ensure_usage_analytics_available(session)
    validated_days = validate_window_days(days)
    scope_space_id = scope_space_id_for_request(
        current_space_id=space_ctx.space_id,
        all_spaces=all_spaces,
        requested_space_id=space_id,
    )
    validate_requested_analytics_space(session, scope_space_id=scope_space_id)
    return build_summary_payload(
        session,
        days=validated_days,
        all_spaces=all_spaces,
        scope_space_id=scope_space_id,
    )


@router.get("/routes", response_model=AnalyticsRouteStatsRead)
def get_usage_analytics_routes(
    days: int = 30,
    all_spaces: bool = False,
    space_id: str | None = None,
    session: Session = Depends(get_db),
    _global_admin: User = Depends(require_global_admin),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    ensure_usage_analytics_available(session)
    validated_days = validate_window_days(days)
    scope_space_id = scope_space_id_for_request(
        current_space_id=space_ctx.space_id,
        all_spaces=all_spaces,
        requested_space_id=space_id,
    )
    validate_requested_analytics_space(session, scope_space_id=scope_space_id)
    return build_route_stats_payload(
        session,
        days=validated_days,
        all_spaces=all_spaces,
        scope_space_id=scope_space_id,
    )


@router.get("/performance", response_model=AnalyticsPerformanceStatsRead)
def get_usage_analytics_performance(
    days: int = 30,
    all_spaces: bool = False,
    space_id: str | None = None,
    session: Session = Depends(get_db),
    _global_admin: User = Depends(require_global_admin),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    ensure_usage_analytics_available(session)
    validated_days = validate_window_days(days)
    scope_space_id = scope_space_id_for_request(
        current_space_id=space_ctx.space_id,
        all_spaces=all_spaces,
        requested_space_id=space_id,
    )
    validate_requested_analytics_space(session, scope_space_id=scope_space_id)
    return build_performance_stats_payload(
        session,
        days=validated_days,
        all_spaces=all_spaces,
        scope_space_id=scope_space_id,
    )


@router.get("/dashboard", response_model=AnalyticsDashboardRead)
def get_usage_analytics_dashboard(
    days: int = 30,
    all_spaces: bool = False,
    space_id: str | None = None,
    session: Session = Depends(get_db),
    _global_admin: User = Depends(require_global_admin),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    ensure_usage_analytics_available(session)
    validated_days = validate_window_days(days)
    scope_space_id = scope_space_id_for_request(
        current_space_id=space_ctx.space_id,
        all_spaces=all_spaces,
        requested_space_id=space_id,
    )
    validate_requested_analytics_space(session, scope_space_id=scope_space_id)
    return build_dashboard_payload(
        session,
        days=validated_days,
        all_spaces=all_spaces,
        scope_space_id=scope_space_id,
    )


__all__ = ["router"]
