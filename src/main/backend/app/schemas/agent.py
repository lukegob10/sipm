from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentManifestRead(BaseModel):
    name: str
    version: str
    context_path: str
    requires_space_id: bool
    space_discovery_requires_space_id: bool
    space_discovery_path: str
    auth: dict[str, Any]
    capabilities: list[str]
    writable_entities: list[str]
    writable_actions: list[str]
    writes_require_change_request: bool
    human_review_required: bool
    service_account_can_approve: bool
    human_delegated_review: bool
    max_patch_operations: int


class AgentErrorRead(BaseModel):
    code: str
    message: str
    request_id: str
    details: Any = Field(default_factory=dict)


class AgentSpaceRead(BaseModel):
    space_id: str
    name: str
    slug: str
    space_kind: str
    role: str
    updated_at: datetime


class AgentSpaceListRead(BaseModel):
    records: list[AgentSpaceRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentPersonRead(BaseModel):
    user_id: str
    soeid: str
    display_name: str
    membership_role: str
    team_tag: str | None = None
    capacity_hours: int
    capacity_fte_month: float
    is_service_account: bool
    updated_at: datetime


class AgentPeopleListRead(BaseModel):
    space_id: str
    records: list[AgentPersonRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentTeamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_id: str
    name: str
    description: str | None = None
    lead: str | None = None
    default_capacity_per_week: int
    default_capacity_fte_month: float
    capacity_unit: str
    member_count: int = 0
    created_at: datetime
    updated_at: datetime


class AgentTeamListRead(BaseModel):
    space_id: str
    records: list[AgentTeamRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentTeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    team_member_id: str
    team_id: str
    member_name: str
    role: str
    capacity_override: int | None = None
    capacity_unit: str | None = None
    hours_capacity: int | None = None
    capacity_fte_month: float | None = None
    points_capacity: int | None = None
    percent_capacity: float | None = None
    created_at: datetime
    updated_at: datetime


class AgentTeamMemberListRead(BaseModel):
    space_id: str
    team_id: str
    records: list[AgentTeamMemberRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentProgramNode(BaseModel):
    program_id: str
    program_name: str
    description: str | None = None
    created_at: datetime | None = None
    updated_at: datetime


class AgentProgramRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    program_id: str
    program_name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class AgentProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: str
    program_id: str
    program_name: str | None = None
    project_name: str
    function: str | None = None
    area: str | None = None
    status: str
    description: str | None = None
    success_criteria: str | None = None
    sponsor: str | None = None
    sponsor_user_soeid: str | None = None
    owner: str | None = None
    owner_user_soeid: str | None = None
    strategic_objective: str | None = None
    priority: int | None = None
    created_at: datetime
    updated_at: datetime


class AgentSolutionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    solution_id: str
    project_id: str
    solution_name: str
    version: str
    github_repo_url: str | None = None
    status: str
    rag_status: str
    rag_reason: str | None = None
    priority: int
    due_date: date | None = None
    planned_start_date: date | None = None
    current_phase: str | None = None
    description: str | None = None
    success_criteria: str | None = None
    problem_statement: str | None = None
    escalation: str | None = None
    owner: str | None = None
    owner_user_soeid: str | None = None
    assignee: str | None = None
    assignee_user_soeid: str | None = None
    approver: str | None = None
    approver_user_soeid: str | None = None
    key_stakeholder: str | None = None
    blockers: str | None = None
    risks: str | None = None
    impact_confidence: str | None = None
    rag_confidence: float | None = None
    completed_at: datetime | None = None
    capacity_hours: int | None = None
    created_at: datetime
    updated_at: datetime


class AgentTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    project_id: str
    solution_id: str
    task_name: str
    description: str | None = None
    github_repo_url: str | None = None
    effective_github_repo_url: str | None = None
    repo_source: str = "none"
    status: str
    priority: int
    due_date: date | None = None
    assignee: str | None = None
    assignee_user_soeid: str | None = None
    estimate_hours: int | None = None
    blocked: bool | None = None
    blocker_note: str | None = None
    acceptance_criteria: str | None = None
    done_criteria: str | None = None
    completed_at: datetime | None = None
    capacity_hours: int | None = None
    is_overdue: bool = False
    is_due_soon: bool = False
    is_stale: bool = False
    urgency_score: float = 0
    created_at: datetime
    updated_at: datetime


class AgentAssignedWorkItemRead(BaseModel):
    task: AgentTaskRead
    program_id: str | None = None
    program_name: str | None = None
    project_name: str
    solution_name: str
    needs_attention: bool = False


class AgentAssignedWorkListRead(BaseModel):
    space_id: str
    assignee_user_soeid: str
    records: list[AgentAssignedWorkItemRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentWorkItemSummary(BaseModel):
    entity_type: str
    entity_id: str
    name: str
    program_id: str | None = None
    project_id: str | None = None
    solution_id: str | None = None
    status: str | None = None
    priority: int | None = None
    due_date: date | None = None
    owner_user_soeid: str | None = None
    assignee_user_soeid: str | None = None
    sponsor_user_soeid: str | None = None
    approver_user_soeid: str | None = None
    lifecycle: str = "active"
    created_at: datetime
    updated_at: datetime


class AgentWorkItemListRead(BaseModel):
    space_id: str
    entity_type: str
    records: list[AgentWorkItemSummary]
    next_cursor: str | None = None
    has_more: bool = False


class AgentAuditRecordRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    change_id: str
    entity_type: str
    entity_id: str
    action: str
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    user_id: str
    space_id: str | None = None
    request_id: str | None = None
    created_at: datetime


class AgentAuditFeedRead(BaseModel):
    space_id: str
    records: list[AgentAuditRecordRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentReferenceDataRead(BaseModel):
    version: str
    entity_types: list[str]
    operations: list[str]
    fields: dict[str, dict[str, list[str]]]
    statuses: dict[str, list[str]]
    status_transitions: dict[str, dict[str, list[str]]]
    rag_statuses: list[str]
    confidence_levels: list[str]
    phases: list[dict[str, Any]]
    limits: dict[str, int]
    filters: dict[str, list[str]]


class AgentTaskNode(BaseModel):
    task_id: str
    project_id: str
    solution_id: str
    task_name: str
    description: str | None = None
    status: str
    priority: int | None = None
    assignee: str | None = None
    assignee_user_soeid: str | None = None
    github_repo_url: str | None = None
    effective_github_repo_url: str | None = None
    repo_source: str | None = None
    due_date: date | None = None
    estimate_hours: int | None = None
    blocked: bool | None = None
    blocker_note: str | None = None
    acceptance_criteria: str | None = None
    done_criteria: str | None = None
    completed_at: datetime | None = None
    capacity_hours: int | None = None
    is_overdue: bool | None = None
    is_due_soon: bool | None = None
    is_stale: bool | None = None
    urgency_score: float | None = None
    created_at: datetime | None = None
    updated_at: datetime


class AgentSolutionNode(BaseModel):
    solution_id: str
    project_id: str
    solution_name: str
    version: str
    status: str
    rag_status: str
    priority: int | None = None
    owner: str | None = None
    owner_user_soeid: str | None = None
    assignee: str | None = None
    assignee_user_soeid: str | None = None
    github_repo_url: str | None = None
    rag_reason: str | None = None
    due_date: date | None = None
    planned_start_date: date | None = None
    current_phase: str | None = None
    description: str | None = None
    success_criteria: str | None = None
    problem_statement: str | None = None
    escalation: str | None = None
    approver: str | None = None
    approver_user_soeid: str | None = None
    key_stakeholder: str | None = None
    blockers: str | None = None
    risks: str | None = None
    impact_confidence: str | None = None
    rag_confidence: float | None = None
    completed_at: datetime | None = None
    capacity_hours: int | None = None
    created_at: datetime | None = None
    updated_at: datetime
    tasks: list[AgentTaskNode] = Field(default_factory=list)


class AgentProjectNode(BaseModel):
    project_id: str
    program_id: str
    program_name: str | None = None
    project_name: str
    status: str
    priority: int | None = None
    sponsor: str | None = None
    sponsor_user_soeid: str | None = None
    owner: str | None = None
    owner_user_soeid: str | None = None
    description: str | None = None
    success_criteria: str | None = None
    strategic_objective: str | None = None
    created_at: datetime | None = None
    updated_at: datetime
    solutions: list[AgentSolutionNode] = Field(default_factory=list)


class AgentWorkGraphRead(BaseModel):
    space_id: str
    projection: str = "summary"
    filter_semantics: str = "parent_match_full_children"
    programs: list[AgentProgramNode] = Field(default_factory=list)
    records: list[AgentProjectNode]
    next_cursor: str | None = None
    has_more: bool = False


class AgentPatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_operation_id: str = Field(min_length=1)
    op: str = Field(min_length=1)
    entity: str = Field(min_length=1)
    ref: str | None = None
    id: str | None = None
    if_updated_at: datetime | None = None
    program_ref: str | None = None
    project_id: str | None = None
    project_ref: str | None = None
    solution_id: str | None = None
    solution_ref: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class AgentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    reason: str | None = None
    idempotency_key: str | None = None
    operations: list[AgentPatchOperation] = Field(min_length=1, max_length=25)


class AgentChangeRequestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    if_request_updated_at: datetime
    reason: str = Field(min_length=1)
    operations: list[AgentPatchOperation] = Field(min_length=1, max_length=25)


class AgentPatchOperationResult(BaseModel):
    client_operation_id: str
    op: str
    entity: str
    ref: str | None = None
    valid: bool
    applied: bool = False
    entity_id: str | None = None
    updated_at: datetime | None = None
    code: str | None = None
    message: str | None = None


class AgentPatchResponse(BaseModel):
    valid: bool
    applied: bool
    dry_run: bool
    operation_count: int
    results: list[AgentPatchOperationResult]


class AgentChangeRequestReview(BaseModel):
    review_note: str | None = None


class AgentDelegatedChangeRequestReview(BaseModel):
    confirm_change_request_id: str = Field(min_length=1)
    if_request_updated_at: datetime
    review_note: str | None = None


class AgentDelegatedTokenRead(BaseModel):
    token_type: str = "bearer"
    access_token: str
    expires_in_seconds: int


class AgentChangeRequestOperationReview(BaseModel):
    client_operation_ids: list[str] = Field(min_length=1, max_length=25)
    review_note: str | None = None


class AgentChangeRequestBulkReview(BaseModel):
    change_request_ids: list[str] = Field(min_length=1, max_length=50)
    review_note: str | None = None


class AgentChangeRequestDiffItem(BaseModel):
    client_operation_id: str
    op: str
    entity: str
    entity_id: str | None = None
    entity_ref: str | None = None
    entity_label: str | None = None
    fields: dict[str, dict[str, Any]]


class AgentChangeRequestRead(BaseModel):
    change_request_id: str
    space_id: str
    proposed_by_user_id: str
    proposed_by_label: str | None = None
    status: str
    reason: str
    idempotency_key: str
    operation_count: int
    operations: list[AgentPatchOperation]
    validation: AgentPatchResponse | None = None
    diff: list[AgentChangeRequestDiffItem]
    created_at: datetime
    updated_at: datetime
    reviewed_by_user_id: str | None = None
    reviewed_at: datetime | None = None
    review_note: str | None = None
    applied_at: datetime | None = None
    failed_reason: str | None = None


class AgentChangeRequestListRead(BaseModel):
    space_id: str
    status: str
    pending_count: int
    failed_count: int
    records: list[AgentChangeRequestRead]
    next_cursor: str | None = None
    has_more: bool = False


class AgentChangeRequestBulkReviewResult(BaseModel):
    requested: int
    approved: int = 0
    rejected: int = 0
    failed: int = 0
    records: list[AgentChangeRequestRead]
