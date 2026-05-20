from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.table_names import fk_target, physical_table_name
from .base import Base, SoftDeleteMixin, TimestampMixin, _utcnow_naive, uuid_str


class User(TimestampMixin, Base):
    __tablename__ = physical_table_name("users")
    __table_args__ = (
        UniqueConstraint("email", name="uix_user_email"),
        UniqueConstraint("soeid", name="uix_user_soeid"),
    )

    user_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    soeid: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_service_account: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    team_tag: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    capacity_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    capacity_fte_month: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temp_password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temp_password_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    force_password_reset: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        nullable=True,
    )


class ApiToken(TimestampMixin, Base):
    __tablename__ = physical_table_name("api_tokens")
    __table_args__ = (
        UniqueConstraint("token_hash", name="uix_api_token_hash"),
        Index("idx_api_token_user", "user_id"),
    )

    token_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("users", "user_id")),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by_user_id: Mapped[str] = mapped_column(String, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )


class Space(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("spaces")
    __table_args__ = (
        UniqueConstraint("slug", name="uix_space_slug"),
        UniqueConstraint("name", name="uix_space_name"),
    )

    space_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, index=True
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )


class SpaceMembership(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("space_memberships")
    __table_args__ = (
        UniqueConstraint("space_id", "user_id", name="uix_space_membership"),
    )

    membership_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=uuid_str
    )
    space_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("users", "user_id")),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(
        String, nullable=False, default="member", index=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="active", index=True
    )


class ChangeLog(Base):
    __tablename__ = physical_table_name("change_log")
    __table_args__ = (
        Index("idx_change_entity_created", "entity_type", "entity_id", "created_at"),
        Index("idx_change_user_created", "user_id", "created_at"),
    )

    change_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    request_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=_utcnow_naive,
        nullable=False,
        index=True,
    )


class Team(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("teams")
    __table_args__ = (UniqueConstraint("space_id", "name", name="uix_team_space_name"),)

    team_id: Mapped[str] = mapped_column(String, primary_key=True, default=uuid_str)
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lead: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    default_capacity_per_week: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    default_capacity_fte_month: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    capacity_unit: Mapped[str] = mapped_column(String, nullable=False, default="hours")


class TeamMember(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("team_members")

    team_member_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=uuid_str
    )
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    team_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("teams", "team_id")),
        nullable=False,
        index=True,
    )
    member_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    capacity_override: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hours_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity_fte_month: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    points_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percent_capacity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


__all__ = [
    "ApiToken",
    "ChangeLog",
    "Space",
    "SpaceMembership",
    "Team",
    "TeamMember",
    "User",
]
