from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.table_names import fk_target, physical_table_name
from .base import Base, _utcnow_naive


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

    event_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
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

    sample_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
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


__all__ = [
    "PerformanceSample",
    "UsageEvent",
]
