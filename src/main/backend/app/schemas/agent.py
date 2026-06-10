from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentManifestRead(BaseModel):
    name: str
    version: str
    context_path: str
    requires_space_id: bool
    auth: dict[str, Any]
    capabilities: list[str]
    writable_entities: list[str]
    writable_actions: list[str]
    max_patch_operations: int


class AgentTaskNode(BaseModel):
    task_id: str
    project_id: str
    solution_id: str
    task_name: str
    status: str
    priority: int | None = None
    assignee: str | None = None
    assignee_user_soeid: str | None = None
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
    updated_at: datetime
    solutions: list[AgentSolutionNode] = Field(default_factory=list)


class AgentWorkGraphRead(BaseModel):
    space_id: str
    records: list[AgentProjectNode]


class AgentPatchOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_operation_id: str = Field(min_length=1)
    op: str = Field(min_length=1)
    entity: str = Field(min_length=1)
    id: str | None = None
    if_updated_at: datetime | None = None
    project_id: str | None = None
    solution_id: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)


class AgentPatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    reason: str | None = None
    idempotency_key: str | None = None
    operations: list[AgentPatchOperation] = Field(min_length=1, max_length=25)


class AgentPatchOperationResult(BaseModel):
    client_operation_id: str
    op: str
    entity: str
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


class AgentChangeRequestBulkReview(BaseModel):
    change_request_ids: list[str] = Field(min_length=1, max_length=50)
    review_note: str | None = None


class AgentChangeRequestDiffItem(BaseModel):
    client_operation_id: str
    op: str
    entity: str
    entity_id: str | None = None
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


class AgentChangeRequestBulkReviewResult(BaseModel):
    requested: int
    approved: int = 0
    rejected: int = 0
    failed: int = 0
    records: list[AgentChangeRequestRead]
