from datetime import date, datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.table_names import fk_target, physical_table_name
from ..utils.enums import (
    ConfidenceLevel,
    ProjectStatus,
    RagStatus,
    SolutionStatus,
    TaskStatus,
)
from .base import Base, SoftDeleteMixin, TimestampMixin


class Program(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("programs")
    __table_args__ = (
        UniqueConstraint("space_id", "program_name", name="uix_program_space_name"),
    )

    program_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    program_name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Project(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("projects")
    __table_args__ = (UniqueConstraint("space_id", "project_name", name="uix_project_space_name"),)

    project_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    program_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("programs", "program_id")),
        index=True,
        nullable=False,
    )
    project_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus),
        index=True,
        nullable=False,
        default=ProjectStatus.not_started,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sponsor: Mapped[str] = mapped_column(String, nullable=False, default="")
    sponsor_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    strategic_objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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

    solution_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("projects", "project_id")),
        index=True,
        nullable=False,
    )
    solution_name: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[str] = mapped_column(String, nullable=False, default="0.1.0")
    status: Mapped[SolutionStatus] = mapped_column(
        Enum(SolutionStatus),
        index=True,
        nullable=False,
        default=SolutionStatus.not_started,
    )
    rag_status: Mapped[RagStatus] = mapped_column(
        Enum(RagStatus),
        index=True,
        nullable=False,
        default=RagStatus.green,
    )
    rag_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    current_phase: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    problem_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    github_repo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    owner: Mapped[str] = mapped_column(String, nullable=False, default="")
    owner_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    assignee: Mapped[str] = mapped_column(String, nullable=False, default="", index=True)
    assignee_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    approver: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    approver_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    key_stakeholder: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    blockers: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    impact_confidence: Mapped[Optional[ConfidenceLevel]] = mapped_column(
        Enum(ConfidenceLevel),
        nullable=True,
    )
    planned_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    rag_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    capacity_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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

    solution_phase_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    solution_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("solutions", "solution_id")),
        index=True,
    )
    phase_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("phases", "phase_id")),
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sequence_override: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)


class SolutionDocument(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("solution_documents")

    document_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    solution_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("solutions", "solution_id")),
        index=True,
        nullable=False,
    )
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    uploaded_by_user_id: Mapped[str] = mapped_column(String, nullable=False, index=True)


class Task(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("tasks")
    __table_args__ = (
        UniqueConstraint(
            "solution_id",
            "task_name",
            name="uix_task_solution_name",
        ),
    )

    task_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    project_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("projects", "project_id")),
        index=True,
        nullable=False,
    )
    solution_id: Mapped[str] = mapped_column(
        String,
        ForeignKey(fk_target("solutions", "solution_id")),
        index=True,
        nullable=False,
    )
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus),
        index=True,
        nullable=False,
        default=TaskStatus.to_do,
    )
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assignee_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    assignee: Mapped[str] = mapped_column(String, nullable=False, default="")
    github_repo_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    estimate_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    blocker_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    done_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capacity_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


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
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    work_item_type: Mapped[str] = mapped_column(String, nullable=False)
    work_item_id: Mapped[str] = mapped_column(String, nullable=False)
    assignee_user_soeid: Mapped[Optional[str]] = mapped_column(String, nullable=True, index=True)
    assignee: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    team_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("teams", "team_id")),
        nullable=True,
        index=True,
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    month_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    fte_months: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    window_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("planning_windows", "window_id")),
        nullable=True,
        index=True,
    )


class PlanningWindow(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = physical_table_name("planning_windows")
    __table_args__ = (
        UniqueConstraint("name", name="uix_planning_window_name"),
    )

    window_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    space_id: Mapped[Optional[str]] = mapped_column(
        String,
        ForeignKey(fk_target("spaces", "space_id")),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)


__all__ = [
    "Phase",
    "PlanningWindow",
    "Program",
    "Project",
    "ResourceAllocation",
    "Solution",
    "SolutionDocument",
    "SolutionPhase",
    "Task",
]
