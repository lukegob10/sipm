from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.table_names import fk_target, physical_table_name
from .base import Base, TimestampMixin


class AgentChangeRequest(TimestampMixin, Base):
    __tablename__ = physical_table_name("agent_change_requests")
    __table_args__ = (
        Index("idx_agent_cr_space_status", "space_id", "status", "created_at"),
        Index("idx_agent_cr_proposer", "proposed_by_user_id", "created_at"),
    )

    change_request_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    space_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=False,
        index=True,
    )
    proposed_by_user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("users", "user_id")),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    reason: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False)
    operations_json: Mapped[str] = mapped_column(Text, nullable=False)
    validation_json: Mapped[str] = mapped_column(Text, nullable=False)
    diff_json: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_by_user_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("users", "user_id")),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    failed_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
