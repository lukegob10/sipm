from datetime import datetime, date
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, constr

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
    new_password: str
    confirm_password: str


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


class GenAIRequest(BaseModel):
    entity_type: str  # project|solution|subcomponent
    entity_id: Optional[str] = None
    instruction: Optional[str] = None
    history: Optional[list["GenAIMessage"]] = None
    current_date: Optional[str] = None


class GenAIResponse(BaseModel):
    output: str


class GenAIApproveRequest(BaseModel):
    request_type: str  # autofill|sow|checklist|subcomponents
    entity_type: str  # project|solution|subcomponent
    entity_id: Optional[str] = None
    output: str
    month_key: Optional[str] = None
    audit_tools: Optional[list[str]] = None


class GenAISearchRequest(BaseModel):
    query: str
    limit: int = 10


class GenAISearchResult(BaseModel):
    entity_type: str
    entity_id: str
    label: str


class GenAISearchResponse(BaseModel):
    results: list[GenAISearchResult]


class GenAIIntentRequest(BaseModel):
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    history: Optional[list["GenAIMessage"]] = None
    current_date: Optional[str] = None


class GenAIIntentResponse(BaseModel):
    intent: str
    reply: str


class GenAIMessage(BaseModel):
    role: str
    content: str


class AIChatRequest(BaseModel):
    message: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    history: Optional[list[GenAIMessage]] = None
    current_date: Optional[str] = None


class AIChatResponse(BaseModel):
    reply: str
    requires_approval: bool = False
    request_type: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    output: Optional[str] = None
    session_id: Optional[str] = None
    next_action: Optional[str] = None
    debug: Optional[dict] = None


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


# ------------------------------
# Document Workbench Schemas
# ------------------------------


class WorkbenchTemplateResponse(BaseModel):
    doc_type: str
    template: str
    config: dict


class WorkbenchDocSaveRequest(BaseModel):
    project_id: str
    title: Optional[str] = None
    content: str


class WorkbenchDocRevisionSummary(BaseModel):
    revision_id: str
    title: Optional[str] = None
    state: str
    created_at: datetime
    created_by_user_id: Optional[str] = None
    approval_state: Optional[str] = None


class WorkbenchDocRevisionResponse(BaseModel):
    doc_type: str
    revision_id: str
    project_id: str
    title: Optional[str] = None
    content: str
    state: str
    approval_state: Optional[str] = None
    approval_note: Optional[str] = None
    created_at: datetime
    created_by_user_id: Optional[str] = None


class WorkbenchDocListResponse(BaseModel):
    doc_type: str
    project_id: str
    revisions: list[WorkbenchDocRevisionSummary]


class WorkbenchValidationError(BaseModel):
    code: str
    message: str
    section: Optional[str] = None


class WorkbenchValidateRequest(BaseModel):
    doc_type: str
    content: str
    state: str = "draft"


class WorkbenchValidateResponse(BaseModel):
    ok: bool
    errors: list[WorkbenchValidationError] = []


class WorkbenchRefineRequest(BaseModel):
    doc_type: str
    project_id: str
    content: str
    assist_level: str = "light"


class WorkbenchRefinePatch(BaseModel):
    op: str
    content: Optional[str] = None


class WorkbenchRefineResponse(BaseModel):
    patches: list[WorkbenchRefinePatch] = []
    summary: str = ""
    questions: list[str] = []
    warnings: list[str] = []


class WorkbenchChecklistItemRead(BaseModel):
    checklist_id: str
    title: str
    status: str
    created_at: datetime


class WorkbenchChecklistReadResponse(BaseModel):
    project_id: str
    month_key: str
    items: list[WorkbenchChecklistItemRead]


class WorkbenchChecklistSaveRequest(BaseModel):
    project_id: str
    month_key: str
    items: list[str]


class WorkbenchChecklistGenerateRequest(BaseModel):
    project_id: str
    month_key: str


class WorkbenchChecklistGenerateResponse(BaseModel):
    checklist: list[str] = []
    summary: str = ""
    questions: list[str] = []
    warnings: list[str] = []
    markdown: str = ""


# ------------------------------
# Structure Studio Schemas
# ------------------------------


class StructureStudioEvidence(BaseModel):
    doc_type: str
    revision_id: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    excerpt: Optional[str] = None


class StructureStudioDraftItem(BaseModel):
    draft_id: str
    kind: str
    name: str
    description: Optional[str] = None
    parent_solution_draft_id: Optional[str] = None
    status: str = "draft"
    user_edited_fields: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[StructureStudioEvidence] = Field(default_factory=list)
    confidence: Optional[str] = None


class StructureStudioDraftPayload(BaseModel):
    solutions: list[StructureStudioDraftItem] = Field(default_factory=list)
    subcomponents: list[StructureStudioDraftItem] = Field(default_factory=list)


class StructureStudioSourceDoc(BaseModel):
    doc_type: str
    revision_id: Optional[str] = None
    title: Optional[str] = None
    state: Optional[str] = None
    created_at: Optional[datetime] = None
    content: str = ""


class StructureStudioSources(BaseModel):
    charter: Optional[StructureStudioSourceDoc] = None
    plan: Optional[StructureStudioSourceDoc] = None


class StructureStudioSufficiency(BaseModel):
    status: str
    missing: list[str] = Field(default_factory=list)
    objective_detected: bool = False
    summary: str = ""


class StructureStudioContextResponse(BaseModel):
    project_id: str
    sufficiency: StructureStudioSufficiency
    sources: StructureStudioSources


class StructureStudioGenerateRequest(BaseModel):
    project_id: str
    allow_minimal_on_insufficient: bool = False
    decomposition_level: Literal["simple", "detailed"] = "simple"


class StructureStudioGenerateResponse(BaseModel):
    project_id: str
    sufficiency: StructureStudioSufficiency
    draft: StructureStudioDraftPayload
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    minimal_draft: bool = False


class StructureStudioRefineRequest(BaseModel):
    project_id: str
    instruction: str
    draft: StructureStudioDraftPayload
    target_ids: list[str] = Field(default_factory=list)
    allow_full_regeneration: bool = False
    locked_fields_by_item: dict[str, list[str]] = Field(default_factory=dict)
    decomposition_level: Literal["simple", "detailed"] = "simple"


class StructureStudioRefineOperation(BaseModel):
    op: str
    item_id: Optional[str] = None
    target_id: Optional[str] = None
    kind: Optional[str] = None
    fields: dict[str, Any] = Field(default_factory=dict)
    items: list[StructureStudioDraftItem] = Field(default_factory=list)
    reason: str = ""


class StructureStudioRefineResponse(BaseModel):
    operations: list[StructureStudioRefineOperation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class StructureStudioCommitAccepted(BaseModel):
    solution_ids: list[str] = Field(default_factory=list)
    subcomponent_ids: list[str] = Field(default_factory=list)


class StructureStudioCommitRequest(BaseModel):
    project_id: str
    draft: StructureStudioDraftPayload
    accepted: StructureStudioCommitAccepted


class StructureStudioCreatedSolution(BaseModel):
    draft_id: str
    solution_id: str
    solution_name: str


class StructureStudioCreatedSubcomponent(BaseModel):
    draft_id: str
    subcomponent_id: str
    subcomponent_name: str
    solution_id: str


class StructureStudioCommitResponse(BaseModel):
    project_id: str
    created_solutions: list[StructureStudioCreatedSolution] = Field(default_factory=list)
    created_subcomponents: list[StructureStudioCreatedSubcomponent] = Field(default_factory=list)
    discarded_count: int = 0
    warnings: list[str] = Field(default_factory=list)


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
