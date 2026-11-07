from datetime import datetime, date, timezone
from typing import Literal, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, constr, field_validator

from ..utils import MAX_DB_INTEGER, ORACLE_NUMBER_MAGNITUDE_LIMIT, read_text_value
from ..utils.enums import ConfidenceLevel, ProjectStatus, RagStatus, SolutionStatus, TaskStatus
from .agent import (
    AgentChangeRequestBulkReview,
    AgentChangeRequestBulkReviewResult,
    AgentChangeRequestDiffItem,
    AgentChangeRequestListRead,
    AgentChangeRequestOperationReview,
    AgentChangeRequestRead,
    AgentChangeRequestReview,
    AgentManifestRead,
    AgentPatchOperation,
    AgentPatchOperationResult,
    AgentPatchRequest,
    AgentPatchResponse,
    AgentProgramNode,
    AgentProjectNode,
    AgentSolutionNode,
    AgentTaskNode,
    AgentWorkGraphRead,
)
from .analytics import (
    AnalyticsDailyPointRead,
    AnalyticsDashboardRead,
    AnalyticsFailureHotspotRead,
    AnalyticsPerformanceRouteRead,
    AnalyticsPerformanceStatsRead,
    AnalyticsPerformanceSummaryRead,
    AnalyticsRouteStatsRead,
    AnalyticsRouteViewRead,
    AnalyticsScopeRead,
    AnalyticsSummaryCardsRead,
    AnalyticsSummaryRead,
    AnalyticsWorkflowRead,
    PerformanceSampleIn,
    TelemetryBatchIn,
    TelemetryIngestResultRead,
    UsageEventIn,
)
__all__ = [
    "AnalyticsDailyPointRead",
    "AnalyticsDashboardRead",
    "AgentChangeRequestBulkReview",
    "AgentChangeRequestBulkReviewResult",
    "AgentChangeRequestDiffItem",
    "AgentChangeRequestListRead",
    "AgentChangeRequestOperationReview",
    "AgentChangeRequestRead",
    "AgentChangeRequestReview",
    "AgentManifestRead",
    "AgentPatchOperation",
    "AgentPatchOperationResult",
    "AgentPatchRequest",
    "AgentPatchResponse",
    "AgentProgramNode",
    "AgentProjectNode",
    "AgentSolutionNode",
    "AgentTaskNode",
    "AgentWorkGraphRead",
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
    "ProgramCreate",
    "ProgramDashboardReportRequest",
    "ProgramRead",
    "ProgramUpdate",
    "SolutionDocumentRead",
    "TelemetryBatchIn",
    "TelemetryIngestResultRead",
    "UsageEventIn",
]

class TextLikeReadModel(BaseModel):
    @field_validator(
        "old_value",
        "new_value",
        "description",
        "success_criteria",
        "strategic_objective",
        "problem_statement",
        "rag_reason",
        "blockers",
        "risks",
        "blocker_note",
        "private_note",
        "acceptance_criteria",
        "done_criteria",
        mode="before",
        check_fields=False,
    )
    @classmethod
    def _coerce_text_like_values(cls, value):
        return read_text_value(value)


def _validate_user_display_name(value: Optional[str]) -> Optional[str]:
    if value is not None and (not value.strip() or len(value) > 255):
        raise ValueError("must contain text and be 255 characters or fewer")
    return value


class UserBase(BaseModel):
    soeid: str
    display_name: str

    @field_validator("display_name")
    @classmethod
    def valid_display_name(cls, value):
        return _validate_user_display_name(value)


class UserCreate(UserBase):
    password: constr(min_length=8)  # type: ignore[type-arg]


class UserLogin(BaseModel):
    soeid: str
    password: str


class ForgotPasswordRequest(BaseModel):
    identifier: str


class VerifyTempPasswordRequest(BaseModel):
    soeid: str
    temp_password: str


class ResetPasswordRequest(BaseModel):
    soeid: str
    temp_password: str
    new_password: constr(min_length=8)  # type: ignore[type-arg]
    confirm_password: constr(min_length=8)  # type: ignore[type-arg]


class PasswordResetIssueRequest(BaseModel):
    expires_minutes: Optional[int] = Field(default=None, ge=5, le=24 * 60)


class PasswordResetIssueResponse(BaseModel):
    status: str
    temp_password: str
    expires_at: datetime


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    soeid: str
    email: str
    display_name: str
    role: str
    is_active: bool
    team_tag: Optional[str] = None
    capacity_hours: int = 40
    capacity_fte_month: float = 1.0
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class SessionPolicyRead(BaseModel):
    idle_timeout_seconds: int
    warning_seconds: int
    activity_heartbeat_seconds: int


class SessionActivityRead(BaseModel):
    idle_expires_at: datetime


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    team_tag: Optional[str] = None
    capacity_hours: Optional[int] = None
    capacity_fte_month: Optional[float] = None
    is_active: Optional[bool] = None

    @field_validator("display_name")
    @classmethod
    def valid_display_name(cls, value):
        return _validate_user_display_name(value)

    @field_validator("team_tag")
    @classmethod
    def valid_team_tag(cls, value):
        if value is not None and len(value.strip()) > 255:
            raise ValueError("must be 255 characters or fewer")
        return value


class UserPreferenceUpdate(BaseModel):
    developer_mode_enabled: Optional[bool] = None
    theme: Optional[str] = None

    @field_validator("theme")
    @classmethod
    def _validate_theme(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if normalized == "forest":
            return "slate"
        if normalized not in {"dark", "midnight", "slate", "light", "system"}:
            raise ValueError("theme must be dark, midnight, slate, light, or system")
        return normalized


class UserPreferenceRead(BaseModel):
    developer_mode_enabled: bool = False
    theme: str = "dark"
    has_saved_preferences: bool = False


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    expires_at: Optional[datetime] = None

    @field_validator("expires_at")
    @classmethod
    def _require_supported_expiration(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and value.tzinfo is not None:
            try:
                value.astimezone(timezone.utc)
            except OverflowError:
                raise ValueError("expires_at is outside the supported UTC range") from None
        return value

    @field_validator("name")
    @classmethod
    def _normalize_name(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Token name is required")
        return normalized


class ApiTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    token_id: str
    user_id: str
    name: str
    created_by_user_id: str
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ApiTokenIssueResponse(ApiTokenRead):
    token: str


class SpaceCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class PersonalSpaceCreate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


class SpaceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    public_program_dashboard_enabled: Optional[bool] = None


class SpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    space_id: str
    name: str
    slug: str
    is_active: bool
    space_kind: str = "collaboration"
    owner_user_id: Optional[str] = None
    public_program_dashboard_enabled: bool = False
    created_at: datetime
    updated_at: datetime


class SpaceMembershipCreate(BaseModel):
    user_id: str
    role: str = "member"
    status: str = "active"


class SpaceMembershipCreateBySoeid(BaseModel):
    soeid: str
    role: str = "member"
    status: str = "active"


class SpaceMembershipUpdate(BaseModel):
    role: Optional[str] = None
    status: Optional[str] = None


class SpaceMembershipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    membership_id: str
    space_id: str
    user_id: str
    user_soeid: Optional[str] = None
    user_display_name: Optional[str] = None
    user_email: Optional[str] = None
    role: str
    status: str
    created_at: datetime
    updated_at: datetime


class SpaceAccessRequestCreate(BaseModel):
    requested_role: str = "member"


class SpaceAccessRequestReview(BaseModel):
    decision_note: Optional[str] = None


class SpaceAccessRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    request_id: str
    space_id: str
    space_name: Optional[str] = None
    space_slug: Optional[str] = None
    requester_user_id: str
    requester_soeid: Optional[str] = None
    requester_display_name: Optional[str] = None
    requested_role: str
    status: str
    decided_by_user_id: Optional[str] = None
    decided_at: Optional[datetime] = None
    decision_note: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ActiveSpaceSwitchRequest(BaseModel):
    space_id: str


class ActiveSpaceResponse(BaseModel):
    space_id: str
    space_name: str
    space_role: str
    is_global_admin: bool
    space_kind: str = "collaboration"
    owner_user_id: Optional[str] = None
    usage_analytics_enabled: bool = False


class LoginResponse(UserRead):
    preferences: UserPreferenceRead
    spaces: list[SpaceRead]
    active_space: ActiveSpaceResponse


class ChangeLogRead(TextLikeReadModel):
    model_config = ConfigDict(from_attributes=True)

    change_id: str
    entity_type: str
    entity_id: str
    action: str
    field: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    user_id: str
    space_id: Optional[str] = None
    request_id: Optional[str] = None
    created_at: datetime


class ProgramBase(BaseModel):
    program_name: Optional[str] = None
    description: Optional[str] = None


class ProgramCreate(ProgramBase):
    program_name: str


class ProgramUpdate(ProgramBase):
    pass


class ProgramRead(TextLikeReadModel):
    model_config = ConfigDict(from_attributes=True)

    program_id: str
    program_name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ProgramDashboardReportRequest(BaseModel):
    selected_program_ids: list[str] = Field(default_factory=list)
    collapsed_program_ids: list[str] = Field(default_factory=list)
    collapsed_project_ids: list[str] = Field(default_factory=list)


class ProjectBase(BaseModel):
    program_id: Optional[str] = None
    project_name: Optional[str] = None
    function: Optional[str] = None
    area: Optional[str] = None
    status: Optional[ProjectStatus] = None
    description: Optional[str] = None
    success_criteria: Optional[str] = None
    sponsor: Optional[str] = Field(default=None, max_length=255)
    sponsor_user_soeid: Optional[str] = Field(default=None, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=255)
    owner_user_soeid: Optional[str] = Field(default=None, max_length=255)
    strategic_objective: Optional[str] = None
    priority: Optional[int] = None

    @field_validator("function", "area")
    @classmethod
    def project_metadata_fits_column(cls, value):
        if value is not None and len(value.strip()) > 255:
            raise ValueError("must be 255 characters or fewer")
        return value


class ProjectCreate(ProjectBase):
    program_id: Optional[str] = None
    project_name: str
    status: ProjectStatus = ProjectStatus.not_started
    priority: int = 3


class ProjectUpdate(ProjectBase):
    @field_validator("status", "priority", "sponsor")
    @classmethod
    def required_fields_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("must not be null")
        return value


class ProjectRead(TextLikeReadModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    program_id: str
    program_name: Optional[str] = None
    project_name: str
    function: Optional[str] = None
    area: Optional[str] = None
    status: ProjectStatus
    description: Optional[str] = None
    success_criteria: Optional[str] = None
    sponsor: Optional[str] = None
    sponsor_user_soeid: Optional[str] = None
    owner: Optional[str] = None
    owner_user_soeid: Optional[str] = None
    strategic_objective: Optional[str] = None
    priority: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SolutionBase(BaseModel):
    solution_name: Optional[str] = None
    version: Optional[str] = None
    github_repo_url: Optional[str] = None
    status: Optional[SolutionStatus] = None
    rag_status: Optional[RagStatus] = None
    rag_reason: Optional[str] = None
    priority: Optional[int] = None
    due_date: Optional[date] = None
    planned_start_date: Optional[date] = None
    current_phase: Optional[str] = None
    description: Optional[str] = None
    success_criteria: Optional[str] = None
    problem_statement: Optional[str] = None
    escalation: Optional[str] = Field(default=None, max_length=255)
    owner: Optional[str] = Field(default=None, max_length=255)
    owner_user_soeid: Optional[str] = Field(default=None, max_length=255)
    assignee: Optional[str] = Field(default=None, max_length=255)
    assignee_user_soeid: Optional[str] = Field(default=None, max_length=255)
    approver: Optional[str] = Field(default=None, max_length=255)
    approver_user_soeid: Optional[str] = Field(default=None, max_length=255)
    key_stakeholder: Optional[str] = Field(default=None, max_length=255)
    blockers: Optional[str] = None
    risks: Optional[str] = None
    impact_confidence: Optional[ConfidenceLevel] = None
    rag_confidence: Optional[float] = Field(default=None, allow_inf_nan=False, gt=-ORACLE_NUMBER_MAGNITUDE_LIMIT, lt=ORACLE_NUMBER_MAGNITUDE_LIMIT)
    capacity_hours: Optional[int] = None


class SolutionCreate(SolutionBase):
    solution_name: str
    version: str = "0.1.0"
    status: SolutionStatus = SolutionStatus.not_started
    rag_status: RagStatus = RagStatus.green
    priority: int = 3
    owner: Optional[str] = Field(default=None, max_length=255)


class SolutionUpdate(SolutionBase):
    project_id: Optional[str] = None

    @field_validator("status", "owner", "assignee")
    @classmethod
    def required_fields_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("must not be null")
        return value


class SolutionRead(TextLikeReadModel):
    model_config = ConfigDict(from_attributes=True)

    solution_id: str
    project_id: str
    solution_name: str
    version: str
    github_repo_url: Optional[str] = None
    status: SolutionStatus
    rag_status: RagStatus
    rag_reason: Optional[str] = None
    priority: int
    due_date: Optional[date] = None
    planned_start_date: Optional[date] = None
    current_phase: Optional[str] = None
    description: Optional[str] = None
    success_criteria: Optional[str] = None
    problem_statement: Optional[str] = None
    escalation: Optional[str] = None
    owner: Optional[str] = None
    owner_user_soeid: Optional[str] = None
    assignee: Optional[str] = None
    assignee_user_soeid: Optional[str] = None
    approver: Optional[str] = None
    approver_user_soeid: Optional[str] = None
    key_stakeholder: Optional[str] = None
    blockers: Optional[str] = None
    risks: Optional[str] = None
    impact_confidence: Optional[ConfidenceLevel] = None
    rag_confidence: Optional[float] = None
    completed_at: Optional[datetime] = None
    capacity_hours: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SolutionDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: str
    solution_id: str
    filename: str
    content_type: Optional[str] = None
    size_bytes: int
    uploaded_by_user_id: str
    created_at: datetime
    updated_at: datetime


class PhaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    phase_id: str
    phase_group: str
    phase_name: str
    sequence: int
    created_at: datetime
    updated_at: datetime


class SolutionPhaseInput(BaseModel):
    phase_id: str
    is_enabled: bool = True
    sequence_override: Optional[int] = None


class SolutionPhaseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    solution_phase_id: str
    solution_id: str
    phase_id: str
    is_enabled: bool
    sequence_override: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class TaskBase(BaseModel):
    task_name: Optional[str] = None
    description: Optional[str] = None
    github_repo_url: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[int] = None
    due_date: Optional[date] = None
    assignee: Optional[str] = Field(default=None, max_length=255)
    assignee_user_soeid: Optional[str] = Field(default=None, max_length=255)
    estimate_hours: Optional[int] = None
    blocked: Optional[bool] = None
    blocker_note: Optional[str] = None
    acceptance_criteria: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("acceptance_criteria", "done_criteria"),
    )
    capacity_hours: Optional[int] = None


class TaskCreate(TaskBase):
    task_name: str
    status: TaskStatus = TaskStatus.to_do
    priority: int = 3
    assignee: Optional[str] = Field(default=None, max_length=255)


class TaskUpdate(TaskBase):
    @field_validator("status", "priority")
    @classmethod
    def required_fields_cannot_be_null(cls, value):
        if value is None:
            raise ValueError("must not be null")
        return value


class TaskBatchUpdate(BaseModel):
    task_ids: list[str]
    status: Optional[TaskStatus] = None
    priority: Optional[int] = None
    due_date: Optional[date] = None
    due_date_shift_days: Optional[int] = None
    assignee: Optional[str] = Field(default=None, max_length=255)
    assignee_user_soeid: Optional[str] = Field(default=None, max_length=255)
    clear_assignee: bool = False
    blocked: Optional[bool] = None


class TaskRead(TextLikeReadModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    project_id: str
    solution_id: str
    task_name: str
    description: Optional[str] = None
    github_repo_url: Optional[str] = None
    effective_github_repo_url: Optional[str] = None
    repo_source: str = "none"
    status: TaskStatus
    priority: int
    due_date: Optional[date] = None
    assignee: Optional[str] = None
    assignee_user_soeid: Optional[str] = None
    estimate_hours: Optional[int] = None
    blocked: Optional[bool] = None
    blocker_note: Optional[str] = None
    acceptance_criteria: Optional[str] = None
    done_criteria: Optional[str] = None
    completed_at: Optional[datetime] = None
    capacity_hours: Optional[int] = None
    is_overdue: bool = False
    is_due_soon: bool = False
    is_stale: bool = False
    urgency_score: float = 0
    created_at: datetime
    updated_at: datetime


class UserTaskStateUpdate(BaseModel):
    bucket: Literal["today", "later"] = "later"
    sort_rank: int = Field(default=0, ge=0, le=2_147_483_647)
    reminder_at: Optional[datetime] = None
    private_note: Optional[str] = Field(default=None, max_length=10_000)

    @field_validator("reminder_at")
    @classmethod
    def _require_reminder_timezone(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None:
            if value.utcoffset() is None:
                raise ValueError("reminder_at must include a timezone offset")
            try:
                value.astimezone(timezone.utc)
            except OverflowError:
                raise ValueError("reminder_at is outside the supported UTC range") from None
        return value

    @field_validator("private_note", mode="before")
    @classmethod
    def _normalize_private_note(cls, value):
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("private_note must be a string or null")
        normalized = value.strip()
        return normalized or None


class UserTaskStateRead(TextLikeReadModel):
    task_id: str
    bucket: Literal["today", "later"] = "later"
    sort_rank: int = 0
    reminder_at: Optional[datetime] = None
    private_note: Optional[str] = None


class MyWorkItemRead(TextLikeReadModel):
    task: TaskRead
    program_id: Optional[str] = None
    program_name: Optional[str] = None
    project_name: str
    solution_name: str
    private_bucket: Literal["today", "later"] = "later"
    private_sort_rank: int = 0
    private_reminder_at: Optional[datetime] = None
    private_note: Optional[str] = None
    reminder_due: bool = False
    needs_attention: bool = False


class RepositoryInventoryItemRead(BaseModel):
    github_repo_url: str
    repository_name: str
    program_names: list[str] = Field(default_factory=list)
    project_names: list[str] = Field(default_factory=list)
    solution_names: list[str] = Field(default_factory=list)
    solution_count: int = 0
    task_count: int = 0
    solution_attachment_count: int = 0
    task_override_count: int = 0
    last_updated_at: Optional[datetime] = None


def _validate_team_name(value: Optional[str]) -> Optional[str]:
    if value is not None and (not value.strip() or len(value) > 255):
        raise ValueError("must contain text and be 255 characters or fewer")
    return value


class TeamMemberBase(BaseModel):
  member_name: Optional[str] = None
  role: Optional[str] = Field(default=None, max_length=255)
  capacity_override: Optional[int] = Field(default=None, ge=-MAX_DB_INTEGER - 1, le=MAX_DB_INTEGER)
  capacity_unit: Optional[str] = Field(default=None, max_length=255)
  hours_capacity: Optional[int] = None
  capacity_fte_month: Optional[float] = None
  points_capacity: Optional[int] = Field(default=None, ge=-MAX_DB_INTEGER - 1, le=MAX_DB_INTEGER)
  percent_capacity: Optional[float] = Field(default=None, allow_inf_nan=False, gt=-ORACLE_NUMBER_MAGNITUDE_LIMIT, lt=ORACLE_NUMBER_MAGNITUDE_LIMIT)

  @field_validator("member_name")
  @classmethod
  def validate_member_name(cls, value):
    return _validate_team_name(value)


class TeamMemberCreate(TeamMemberBase):
  member_name: str
  role: str = Field(default="member", max_length=255)


class TeamMemberUpdate(TeamMemberBase):
  pass


class TeamMemberRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  team_member_id: str
  team_id: str
  member_name: str
  role: str
  capacity_override: Optional[int] = None
  capacity_unit: Optional[str] = None
  hours_capacity: Optional[int] = None
  capacity_fte_month: Optional[float] = None
  points_capacity: Optional[int] = None
  percent_capacity: Optional[float] = None
  created_at: datetime
  updated_at: datetime


class TeamBase(BaseModel):
  name: Optional[str] = None
  description: Optional[str] = Field(default=None, max_length=255)
  lead: Optional[str] = Field(default=None, max_length=255)
  default_capacity_per_week: Optional[int] = None
  default_capacity_fte_month: Optional[float] = None
  capacity_unit: Optional[str] = Field(default=None, max_length=255)

  @field_validator("name")
  @classmethod
  def validate_name(cls, value):
    return _validate_team_name(value)


class TeamCreate(TeamBase):
  name: str
  default_capacity_per_week: int = 0
  default_capacity_fte_month: float = 0.0
  capacity_unit: str = Field(default="fte_month", max_length=255)


class TeamUpdate(TeamBase):
  pass


class TeamRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  team_id: str
  name: str
  description: Optional[str] = None
  lead: Optional[str] = None
  default_capacity_per_week: int
  default_capacity_fte_month: float = 0.0
  capacity_unit: str
  created_at: datetime
  updated_at: datetime
  members: list[TeamMemberRead] = []
