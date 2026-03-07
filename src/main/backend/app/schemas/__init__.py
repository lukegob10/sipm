from datetime import datetime, date
from typing import Optional

from pydantic import BaseModel, ConfigDict, constr

from ..utils.enums import ConfidenceLevel, ProjectStatus, RagStatus, SolutionStatus, SubcomponentStatus


class UserBase(BaseModel):
    soeid: str
    display_name: str


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
    new_password: str
    confirm_password: str


class PasswordResetIssueRequest(BaseModel):
    expires_minutes: Optional[int] = None


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


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    team_tag: Optional[str] = None
    capacity_hours: Optional[int] = None
    capacity_fte_month: Optional[float] = None
    is_active: Optional[bool] = None


class SpaceCreate(BaseModel):
    name: str
    slug: Optional[str] = None


class SpaceUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class SpaceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    space_id: str
    name: str
    slug: str
    is_active: bool
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


class ActiveSpaceSwitchRequest(BaseModel):
    space_id: str


class ActiveSpaceResponse(BaseModel):
    space_id: str
    space_name: str
    space_role: str
    is_global_admin: bool


class ChangeLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    change_id: str
    entity_type: str
    entity_id: str
    action: str
    field: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    user_id: str
    request_id: Optional[str] = None
    created_at: datetime


class ProjectBase(BaseModel):
    project_name: Optional[str] = None
    status: Optional[ProjectStatus] = None
    description: Optional[str] = None
    success_criteria: Optional[str] = None
    sponsor: Optional[str] = None
    sponsor_user_soeid: Optional[str] = None
    strategic_objective: Optional[str] = None
    priority: Optional[int] = None


class ProjectCreate(ProjectBase):
    project_name: str
    status: ProjectStatus = ProjectStatus.not_started
    priority: int = 3


class ProjectUpdate(ProjectBase):
    pass


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    project_name: str
    status: ProjectStatus
    description: Optional[str] = None
    success_criteria: Optional[str] = None
    sponsor: Optional[str] = None
    sponsor_user_soeid: Optional[str] = None
    strategic_objective: Optional[str] = None
    priority: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class SolutionBase(BaseModel):
    solution_name: Optional[str] = None
    version: Optional[str] = None
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
    capacity_hours: Optional[int] = None


class SolutionCreate(SolutionBase):
    solution_name: str
    version: str = "0.1.0"
    status: SolutionStatus = SolutionStatus.not_started
    rag_status: RagStatus = RagStatus.green
    priority: int = 3
    owner: Optional[str] = None


class SolutionUpdate(SolutionBase):
    pass


class SolutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    solution_id: str
    project_id: str
    solution_name: str
    version: str
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


class SubcomponentBase(BaseModel):
    subcomponent_name: Optional[str] = None
    status: Optional[SubcomponentStatus] = None
    priority: Optional[int] = None
    due_date: Optional[date] = None
    assignee: Optional[str] = None
    assignee_user_soeid: Optional[str] = None
    estimate_hours: Optional[int] = None
    blocked: Optional[bool] = None
    blocker_note: Optional[str] = None
    done_criteria: Optional[str] = None
    capacity_hours: Optional[int] = None


class SubcomponentCreate(SubcomponentBase):
    subcomponent_name: str
    status: SubcomponentStatus = SubcomponentStatus.to_do
    priority: int = 3
    assignee: Optional[str] = None


class SubcomponentUpdate(SubcomponentBase):
    pass


class SubcomponentBatchUpdate(BaseModel):
    subcomponent_ids: list[str]
    status: Optional[SubcomponentStatus] = None
    priority: Optional[int] = None
    due_date: Optional[date] = None
    due_date_shift_days: Optional[int] = None
    assignee: Optional[str] = None
    assignee_user_soeid: Optional[str] = None
    clear_assignee: bool = False
    blocked: Optional[bool] = None


class SubcomponentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    subcomponent_id: str
    project_id: str
    solution_id: str
    subcomponent_name: str
    status: SubcomponentStatus
    priority: int
    due_date: Optional[date] = None
    assignee: Optional[str] = None
    assignee_user_soeid: Optional[str] = None
    estimate_hours: Optional[int] = None
    blocked: Optional[bool] = None
    blocker_note: Optional[str] = None
    done_criteria: Optional[str] = None
    completed_at: Optional[datetime] = None
    capacity_hours: Optional[int] = None
    is_overdue: bool = False
    is_due_soon: bool = False
    is_stale: bool = False
    urgency_score: float = 0
    created_at: datetime
    updated_at: datetime


class TeamMemberBase(BaseModel):
  member_name: Optional[str] = None
  role: Optional[str] = None
  capacity_override: Optional[int] = None
  capacity_unit: Optional[str] = None
  hours_capacity: Optional[int] = None
  capacity_fte_month: Optional[float] = None
  points_capacity: Optional[int] = None
  percent_capacity: Optional[float] = None


class TeamMemberCreate(TeamMemberBase):
  member_name: str
  role: str = "member"


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
  description: Optional[str] = None
  lead: Optional[str] = None
  default_capacity_per_week: Optional[int] = None
  default_capacity_fte_month: Optional[float] = None
  capacity_unit: Optional[str] = None


class TeamCreate(TeamBase):
  name: str
  default_capacity_per_week: int = 0
  default_capacity_fte_month: float = 0.0
  capacity_unit: str = "fte_month"


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


class PlanningWindowBase(BaseModel):
  name: Optional[str] = None
  start_date: Optional[date] = None
  end_date: Optional[date] = None


class PlanningWindowCreate(PlanningWindowBase):
  name: str
  start_date: date
  end_date: date


class PlanningWindowUpdate(PlanningWindowBase):
  pass


class PlanningWindowRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  window_id: str
  name: str
  start_date: date
  end_date: date
  created_at: datetime
  updated_at: datetime


class ResourceAllocationBase(BaseModel):
  work_item_type: Optional[str] = None  # project|solution|subcomponent
  work_item_id: Optional[str] = None
  assignee: Optional[str] = None
  assignee_user_soeid: Optional[str] = None
  team_id: Optional[str] = None
  month_start: Optional[date] = None
  fte_months: Optional[float] = None
  week_start: Optional[date] = None
  hours: Optional[int] = None
  window_id: Optional[str] = None


class ResourceAllocationCreate(ResourceAllocationBase):
  work_item_type: str
  work_item_id: str
  assignee_user_soeid: Optional[str] = None
  month_start: Optional[date] = None
  fte_months: Optional[float] = None
  week_start: Optional[date] = None
  hours: Optional[int] = None


class ResourceAllocationUpdate(ResourceAllocationBase):
  pass


class ResourceAllocationRead(BaseModel):
  model_config = ConfigDict(from_attributes=True)

  allocation_id: str
  work_item_type: str
  work_item_id: str
  assignee: Optional[str] = None
  assignee_user_soeid: Optional[str] = None
  team_id: Optional[str] = None
  month_start: Optional[date] = None
  fte_months: float = 0.0
  week_start: Optional[date] = None
  hours: int = 0
  window_id: Optional[str] = None
  created_at: datetime
  updated_at: datetime

