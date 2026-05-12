from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


_MAX_DURATION_MS = 24 * 60 * 60 * 1000


def _normalized_token(value: object) -> str:
    return str(value or "").strip().lower().replace(" ", "_").replace("-", "_")


class UsageEventIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    occurred_at: datetime
    session_id: str = Field(min_length=1, max_length=255)
    view_key: str = Field(min_length=1, max_length=255)
    category: str = Field(min_length=1, max_length=255)
    feature_key: str = Field(min_length=1, max_length=255)
    action_key: str = Field(min_length=1, max_length=255)
    outcome: str = Field(min_length=1, max_length=255)
    duration_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    status_code: Optional[int] = Field(default=None, ge=100, le=599)
    details: dict[str, object] = Field(default_factory=dict)

    @field_validator("session_id", "view_key", "category", "feature_key", "action_key", "outcome", mode="before")
    @classmethod
    def _normalize_string_fields(cls, value: object) -> str:
        return _normalized_token(value)


class PerformanceSampleIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    occurred_at: datetime
    session_id: str = Field(min_length=1, max_length=255)
    view_key: str = Field(min_length=1, max_length=255)
    sample_kind: str = Field(min_length=1, max_length=255)
    navigation_type: Optional[str] = Field(default=None, max_length=255)
    data_load_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    render_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    ttfb_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    dom_interactive_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    dom_content_loaded_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    load_event_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    first_paint_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    first_contentful_paint_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    largest_contentful_paint_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)
    cls_score: Optional[float] = Field(default=None, ge=0, le=10)
    long_task_count: Optional[int] = Field(default=None, ge=0, le=100000)
    long_task_total_ms: Optional[int] = Field(default=None, ge=0, le=_MAX_DURATION_MS)

    @field_validator("session_id", "view_key", "sample_kind", "navigation_type", mode="before")
    @classmethod
    def _normalize_string_fields(cls, value: object) -> Optional[str]:
        normalized = _normalized_token(value)
        return normalized or None


class TelemetryBatchIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    events: list[UsageEventIn] = Field(default_factory=list)
    performance_samples: list[PerformanceSampleIn] = Field(default_factory=list)


class TelemetryIngestResultRead(BaseModel):
    status: str
    events_ingested: int
    performance_samples_ingested: int


class AnalyticsScopeRead(BaseModel):
    days: int
    all_spaces: bool
    scope_space_id: Optional[str] = None
    generated_at: datetime


class AnalyticsSummaryCardsRead(BaseModel):
    sessions: int
    active_users: int
    route_views: int
    workflow_actions: int
    failure_count: int
    median_load_ms: Optional[int] = None
    p95_load_ms: Optional[int] = None


class AnalyticsDailyPointRead(BaseModel):
    date: str
    sessions: int
    active_users: int
    route_views: int
    workflow_actions: int
    failure_count: int
    median_load_ms: Optional[int] = None
    p95_load_ms: Optional[int] = None


class AnalyticsSummaryRead(AnalyticsScopeRead):
    summary: AnalyticsSummaryCardsRead
    daily: list[AnalyticsDailyPointRead]


class AnalyticsRouteViewRead(BaseModel):
    view_key: str
    route_views: int
    unique_sessions: int
    active_users: int
    failure_count: int


class AnalyticsWorkflowRead(BaseModel):
    feature_key: str
    action_key: str
    total: int
    success_count: int
    failure_count: int


class AnalyticsFailureHotspotRead(BaseModel):
    view_key: str
    feature_key: str
    action_key: str
    failure_count: int
    last_occurred_at: datetime


class AnalyticsRouteStatsRead(AnalyticsScopeRead):
    top_routes: list[AnalyticsRouteViewRead]
    top_workflows: list[AnalyticsWorkflowRead]
    recent_failures: list[AnalyticsFailureHotspotRead]


class AnalyticsPerformanceSummaryRead(BaseModel):
    navigation_samples: int
    route_transition_samples: int
    median_load_ms: Optional[int] = None
    p95_load_ms: Optional[int] = None


class AnalyticsPerformanceRouteRead(BaseModel):
    view_key: str
    sample_count: int
    median_load_ms: Optional[int] = None
    p95_load_ms: Optional[int] = None
    median_data_load_ms: Optional[int] = None
    p95_data_load_ms: Optional[int] = None
    median_render_ms: Optional[int] = None
    p95_render_ms: Optional[int] = None
    median_first_contentful_paint_ms: Optional[int] = None
    p95_largest_contentful_paint_ms: Optional[int] = None
    avg_cls_score: Optional[float] = None
    long_task_count: int = 0


class AnalyticsPerformanceStatsRead(AnalyticsScopeRead):
    summary: AnalyticsPerformanceSummaryRead
    routes: list[AnalyticsPerformanceRouteRead]


class AnalyticsDashboardRead(BaseModel):
    summary: AnalyticsSummaryRead
    routes: AnalyticsRouteStatsRead
    performance: AnalyticsPerformanceStatsRead


__all__ = [
    "AnalyticsDailyPointRead",
    "AnalyticsDashboardRead",
    "AnalyticsFailureHotspotRead",
    "AnalyticsPerformanceRouteRead",
    "AnalyticsPerformanceStatsRead",
    "AnalyticsPerformanceSummaryRead",
    "AnalyticsRouteStatsRead",
    "AnalyticsRouteViewRead",
    "AnalyticsScopeRead",
    "AnalyticsSummaryCardsRead",
    "AnalyticsSummaryRead",
    "AnalyticsWorkflowRead",
    "PerformanceSampleIn",
    "TelemetryBatchIn",
    "TelemetryIngestResultRead",
    "UsageEventIn",
]
