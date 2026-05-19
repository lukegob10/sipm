from datetime import date, datetime
from typing import Optional

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.table_names import fk_target, physical_table_name
from .base import Base, _utcnow_naive, uuid_str


class UsageEvent(Base):
    __tablename__ = physical_table_name("usage_events")
    __table_args__ = (
        Index("idx_usage_events_created", "occurred_at"),
        Index("idx_usage_events_feature_action_created", "feature_key", "action_key", "occurred_at"),
        Index("idx_usage_events_session_created", "session_id", "occurred_at"),
        Index("idx_usage_events_space_created", "space_id", "occurred_at"),
        Index("idx_usage_events_user_created", "user_id", "occurred_at"),
        Index("idx_usage_events_view_created", "view_key", "occurred_at"),
    )

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
    )
    view_key: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    feature_key: Mapped[str] = mapped_column(String, nullable=False)
    action_key: Mapped[str] = mapped_column(String, nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PerformanceSample(Base):
    __tablename__ = physical_table_name("performance_samples")
    __table_args__ = (
        Index("idx_performance_samples_created", "occurred_at"),
        Index("idx_performance_samples_kind_created", "sample_kind", "occurred_at"),
        Index("idx_performance_samples_session_created", "session_id", "occurred_at"),
        Index("idx_performance_samples_space_created", "space_id", "occurred_at"),
        Index("idx_performance_samples_user_created", "user_id", "occurred_at"),
        Index("idx_performance_samples_view_created", "view_key", "occurred_at"),
    )

    sample_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
    )
    view_key: Mapped[str] = mapped_column(String, nullable=False)
    sample_kind: Mapped[str] = mapped_column(String, nullable=False)
    navigation_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    data_load_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    render_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ttfb_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dom_interactive_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    dom_content_loaded_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    load_event_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_paint_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    first_contentful_paint_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    largest_contentful_paint_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cls_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    long_task_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    long_task_total_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class UsageDailyRollup(Base):
    __tablename__ = physical_table_name("usage_daily_rollups")
    __table_args__ = (
        Index("idx_usage_rollups_space_date", "space_id", "rollup_date"),
        Index("idx_usage_rollups_date_view", "rollup_date", "view_key"),
        Index("idx_usage_rollups_date_workflow", "rollup_date", "category", "feature_key", "action_key"),
        Index("idx_usage_rollups_date_failure", "rollup_date", "outcome", "view_key", "feature_key", "action_key"),
    )

    rollup_date: Mapped[date] = mapped_column(Date, primary_key=True)
    space_id: Mapped[str] = mapped_column(String, primary_key=True)
    view_key: Mapped[str] = mapped_column(String, primary_key=True)
    category: Mapped[str] = mapped_column(String, primary_key=True)
    feature_key: Mapped[str] = mapped_column(String, primary_key=True)
    action_key: Mapped[str] = mapped_column(String, primary_key=True)
    outcome: Mapped[str] = mapped_column(String, primary_key=True)
    event_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    route_view_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    workflow_action_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    success_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)


class UsageIdentityDailyRollup(Base):
    __tablename__ = physical_table_name("usage_identity_daily_rollups")
    __table_args__ = (
        Index("idx_usage_identity_rollups_scope", "space_id", "rollup_date", "token_type"),
        Index("idx_usage_identity_rollups_date", "rollup_date", "token_type"),
    )

    rollup_date: Mapped[date] = mapped_column(Date, primary_key=True)
    space_id: Mapped[str] = mapped_column(String, primary_key=True)
    token_type: Mapped[str] = mapped_column(String, primary_key=True)
    token_value: Mapped[str] = mapped_column(String, primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)


class UsageRouteIdentityDailyRollup(Base):
    __tablename__ = physical_table_name("usage_route_identity_daily_rollups")
    __table_args__ = (
        Index("idx_usage_route_identity_scope", "space_id", "rollup_date", "view_key", "token_type"),
        Index("idx_usage_route_identity_date", "rollup_date", "view_key", "token_type"),
    )

    rollup_date: Mapped[date] = mapped_column(Date, primary_key=True)
    space_id: Mapped[str] = mapped_column(String, primary_key=True)
    view_key: Mapped[str] = mapped_column(String, primary_key=True)
    token_type: Mapped[str] = mapped_column(String, primary_key=True)
    token_value: Mapped[str] = mapped_column(String, primary_key=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, onupdate=_utcnow_naive, nullable=False)


__all__ = [
    "PerformanceSample",
    "UsageDailyRollup",
    "UsageEvent",
    "UsageIdentityDailyRollup",
    "UsageRouteIdentityDailyRollup",
]
