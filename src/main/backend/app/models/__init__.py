from datetime import date, datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Index,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql.sqltypes import String as SQLAlchemyString

from ..db.table_names import fk_target, physical_table_name
from ..utils.enums import (
    ConfidenceLevel,
    ProjectStatus,
    SolutionStatus,
    SubcomponentStatus,
)
from ..utils.enums import RagStatus


class Base(DeclarativeBase):
    metadata = MetaData()


@compiles(SQLAlchemyString, "oracle")
def _compile_oracle_string_with_default_length(type_, compiler, **kw):
    # Oracle table DDL requires VARCHAR2 length; default to 255 when unspecified.
    if type_.length is None:
        return "VARCHAR2(255 CHAR)"
    return compiler.visit_VARCHAR(type_, **kw)


def _utcnow_naive() -> datetime:
    # Keep DB values UTC while preserving naive DateTime column behavior.
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=_utcnow_naive
    )


class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, index=True
    )


class User(TimestampMixin, Base):
    __tablename__ = physical_table_name("users")
    __table_args__ = (
        UniqueConstraint("email", name="uix_user_email"),
        UniqueConstraint("soeid", name="uix_user_soeid"),
    )

    user_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    soeid: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str] = mapped_column(String, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    team_tag: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    capacity_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=40)
    capacity_fte_month: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temp_password_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temp_password_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    force_password_reset: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, default=_utcnow_naive, nullable=True)
    
class PasswordResetToken(TimestampMixin, Base):
    __tablename__ = physical_table_name("password_reset_tokens")
    __table_args__ = (
        UniqueConstraint("token_hash", name="uix_password_reset_token_hash"),
        Index("idx_password_reset_user_expires", "user_id", "expires_at"),
        Index("idx_password_reset_issued_by", "issued_by_user_id", "created_at"),
    )

    reset_token_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=False, index=True)
    issued_by_user_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class Space(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("spaces")
    __table_args__ = (
        UniqueConstraint("slug", name="uix_space_slug"),
        UniqueConstraint("name", name="uix_space_name"),
    )

    space_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String, nullable=False)
    slug: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class SpaceMembership(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("space_memberships")
    __table_args__ = (
        UniqueConstraint("space_id", "user_id", name="uix_space_membership"),
    )

    membership_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member", index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="active", index=True)


class ChangeLog(Base):
    __tablename__ = physical_table_name("change_log")
    __table_args__ = (
        Index("idx_change_entity_created", "entity_type", "entity_id", "created_at"),
        Index("idx_change_user_created", "user_id", "created_at"),
    )

    change_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    entity_type: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[str] = mapped_column(String, nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    old_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow_naive, nullable=False, index=True)


class Team(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("teams")
    __table_args__ = (UniqueConstraint("space_id", "name", name="uix_team_space_name"),)

    team_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    lead: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    default_capacity_per_week: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    default_capacity_fte_month: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    capacity_unit: Mapped[str] = mapped_column(String, nullable=False, default="hours")


class TeamMember(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("team_members")

    team_member_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    team_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("teams", "team_id")), nullable=False, index=True)
    member_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String, nullable=False, default="member")
    capacity_override: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity_unit: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hours_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    capacity_fte_month: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    points_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    percent_capacity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class Project(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("projects")
    __table_args__ = (UniqueConstraint("space_id", "project_name", name="uix_project_space_name"),)

    project_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), index=True, nullable=False, default=ProjectStatus.not_started
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sponsor: Mapped[str] = mapped_column(String, nullable=False, default="")
    sponsor_user_soeid: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    strategic_objective: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)


class Solution(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("solutions")
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "solution_name",
            "version",
            name="uix_solution_project_name_version",
        ),
    )

    solution_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey(fk_target("projects", "project_id")), index=True, nullable=False
    )
    solution_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False, default="0.1.0")
    status: Mapped[SolutionStatus] = mapped_column(
        Enum(SolutionStatus), index=True, nullable=False, default=SolutionStatus.not_started
    )
    rag_status: Mapped[RagStatus] = mapped_column(
        Enum(RagStatus), index=True, nullable=False, default=RagStatus.green
    )
    rag_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    current_phase: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_repo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    owner: Mapped[str] = mapped_column(String, nullable=False, default="")
    owner_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    assignee: Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    assignee_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    approver: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approver_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    key_stakeholder: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blockers: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    risks: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    impact_confidence: Mapped[Optional[ConfidenceLevel]] = mapped_column(
        Enum(ConfidenceLevel), nullable=True
    )
    planned_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rag_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    capacity_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Resource need (hours)


class Phase(TimestampMixin, Base):
    __tablename__ = physical_table_name("phases")

    phase_id: Mapped[str] = mapped_column(String, primary_key=True)
    phase_group: Mapped[str] = mapped_column(String, nullable=False)
    phase_name: Mapped[str] = mapped_column(String, nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, index=True, nullable=False)


class SolutionPhase(TimestampMixin, Base):
    __tablename__ = physical_table_name("solution_phases")
    __table_args__ = (
        UniqueConstraint("solution_id", "phase_id", name="uix_solution_phase"),
    )

    solution_phase_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    solution_id: Mapped[str] = mapped_column(
        String, ForeignKey(fk_target("solutions", "solution_id")), index=True
    )
    phase_id: Mapped[str] = mapped_column(
        String, ForeignKey(fk_target("phases", "phase_id")), nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sequence_override: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, index=True
    )


class Subcomponent(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("subcomponents")
    __table_args__ = (
        UniqueConstraint(
            "solution_id", "subcomponent_name", name="uix_subcomponent_solution_name"
        ),
    )

    subcomponent_id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid4())
    )
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(
        String, ForeignKey(fk_target("projects", "project_id")), index=True, nullable=False
    )
    solution_id: Mapped[str] = mapped_column(
        String, ForeignKey(fk_target("solutions", "solution_id")), index=True, nullable=False
    )
    subcomponent_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[SubcomponentStatus] = mapped_column(
        Enum(SubcomponentStatus), index=True, nullable=False, default=SubcomponentStatus.to_do
    )
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assignee_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    assignee: Mapped[str] = mapped_column(String, nullable=False, default="")
    github_repo_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    estimate_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    blocker_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    done_criteria: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    capacity_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # Resource need (hours)


class ResourceAllocation(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("resource_allocations")
    __table_args__ = (
        Index("idx_alloc_week_assignee", "week_start", "assignee_user_soeid"),
        Index("idx_alloc_month_assignee", "month_start", "assignee_user_soeid"),
        Index("idx_alloc_item", "work_item_type", "work_item_id"),
        UniqueConstraint(
            "work_item_type",
            "work_item_id",
            "assignee_user_soeid",
            "week_start",
            "window_id",
            name="uix_alloc_unique_assignment",
        ),
    )

    allocation_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    work_item_type: Mapped[str] = mapped_column(String, nullable=False)  # project|solution|subcomponent
    work_item_id: Mapped[str] = mapped_column(String, nullable=False)
    assignee_user_soeid: Mapped[Optional[str]] = mapped_column(
        String, nullable=True, index=True
    )
    assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    team_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("teams", "team_id")), nullable=True, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    month_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fte_months: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    window_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("planning_windows", "window_id")), nullable=True, index=True)


class SolutionWeeklySnapshot(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("solution_weekly_snapshot")
    __table_args__ = (
        UniqueConstraint("solution_id", "week_start", name="uix_solution_week_start"),
    )

    snapshot_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    solution_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("solutions", "solution_id")), nullable=False, index=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rag_status: Mapped[RagStatus] = mapped_column(Enum(RagStatus), nullable=False)
    progress_note: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_week_plan: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence_on_due_date: Mapped[Optional[ConfidenceLevel]] = mapped_column(
        Enum(ConfidenceLevel), nullable=True
    )
    owner_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True
    )


class ExternalRef(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("external_ref")
    __table_args__ = (
        UniqueConstraint(
            "work_item_type",
            "work_item_id",
            "ref_type",
            "ref_key",
            name="uix_external_ref_unique",
        ),
        Index("idx_external_ref_work_item", "work_item_type", "work_item_id"),
    )

    external_ref_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    work_item_type: Mapped[str] = mapped_column(String, nullable=False)  # project|solution|subcomponent
    work_item_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    ref_type: Mapped[str] = mapped_column(String, nullable=False)
    ref_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    ref_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class PlanningWindow(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("planning_windows")
    __table_args__ = (
        UniqueConstraint("name", name="uix_planning_window_name"),
    )

    window_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


class SOWDocument(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("sow_documents")

    sow_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    solution_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("solutions", "solution_id")), nullable=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # SOW documents are long-form and regularly exceed Oracle VARCHAR2(255).
    content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    approval_state: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    approval_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approval_requested_by_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True
    )
    approval_decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approval_decided_by_user_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True
    )
    approval_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True)


class ChecklistItem(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("checklist_items")

    checklist_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    month_key: Mapped[str] = mapped_column(String, nullable=False, index=True)  # YYYY-MM
    # Checklist lines may include full markdown table rows and analyst notes.
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="open")
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True)


class ProjectCardDigest(TimestampMixin, Base):
    __tablename__ = physical_table_name("project_card_digests")

    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), primary_key=True)
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    project_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sponsor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    open_solution_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_risks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class SolutionCardDigest(TimestampMixin, Base):
    __tablename__ = physical_table_name("solution_card_digests")

    solution_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("solutions", "solution_id")), primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    solution_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    rag_status: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    current_phase: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    open_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    blocked_task_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    top_risks_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class TaskCardDigest(TimestampMixin, Base):
    __tablename__ = physical_table_name("task_card_digests")

    subcomponent_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("subcomponents", "subcomponent_id")), primary_key=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    solution_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("solutions", "solution_id")), nullable=False, index=True)
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    subcomponent_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    blocker_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimate_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    short_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)


class ProjectCharter(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("project_charters")

    charter_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True)


class ProjectPlan(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("project_plans")

    plan_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String, nullable=False, default="draft", index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True)


class ProjectDecisionLog(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("project_decision_logs")

    decision_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[str] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True)


class ExternalDocument(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("external_documents")

    document_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("spaces", "space_id")), nullable=True, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("projects", "project_id")), nullable=True, index=True)
    solution_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("solutions", "solution_id")), nullable=True, index=True)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    storage_path: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_by_user_id: Mapped[Optional[str]] = mapped_column(String, ForeignKey(fk_target("users", "user_id")), nullable=True, index=True)

