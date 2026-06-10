from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..models import Phase, Project, Solution, Subcomponent, User
from ..routes._mutations import publish_space_mutation
from ..routes.projects.common import (
    _active_project_name_conflict_query,
    _default_program,
    _ensure_program_exists,
    _is_project_name_conflict_integrity_error,
    _project_change_set,
    _project_create_changes,
    _project_query,
    _resolve_project_sponsor,
)
from ..routes.solutions.common import (
    _apply_solution_completion_state,
    _resolve_solution_assignee,
    _resolve_solution_owner,
    _run_enable_all_phases,
    _solution_query,
    _validate_current_phase,
    normalize_github_repo_url as normalize_solution_repo_url,
)
from ..routes.subcomponents.common import (
    _apply_subcomponent_completion_state,
    _ensure_solution,
    _resolve_subcomponent_assignee,
    _solution_query as _subcomponent_solution_query,
    _subcomponent_query,
    normalize_github_repo_url as normalize_subcomponent_repo_url,
)
from ..schemas import ProjectCreate, ProjectUpdate, SolutionCreate, SolutionUpdate
from ..schemas import SubcomponentCreate, SubcomponentUpdate
from ..schemas.agent import (
    AgentPatchOperation,
    AgentPatchOperationResult,
    AgentPatchRequest,
    AgentPatchResponse,
)
from ..services.audit_log import log_changes, safe_log_changes
from ..services.spaces import SpaceContext
from ..utils import normalize_str, parse_priority
from ..utils.enums import SolutionStatus, SubcomponentStatus

VALID_OPS = {"create", "update"}
VALID_ENTITIES = {"project", "solution", "subcomponent"}
PROJECT_FIELDS = set(ProjectCreate.model_fields)
SOLUTION_FIELDS = set(SolutionCreate.model_fields)
SUBCOMPONENT_FIELDS = set(SubcomponentCreate.model_fields)
ENTITY_FIELDS = {
    "project": PROJECT_FIELDS,
    "solution": SOLUTION_FIELDS,
    "subcomponent": SUBCOMPONENT_FIELDS,
}
PUBLISH_KEYS = {
    "project": ("projects",),
    "solution": ("solutions",),
    "subcomponent": ("subcomponents",),
}


def _result(
    operation: AgentPatchOperation,
    *,
    valid: bool,
    applied: bool = False,
    entity_id: str | None = None,
    updated_at: datetime | None = None,
    code: str | None = None,
    message: str | None = None,
) -> AgentPatchOperationResult:
    return AgentPatchOperationResult(
        client_operation_id=operation.client_operation_id,
        op=operation.op,
        entity=operation.entity,
        valid=valid,
        applied=applied,
        entity_id=entity_id,
        updated_at=updated_at,
        code=code,
        message=message,
    )


def _invalid(
    operation: AgentPatchOperation, code: str, message: str
) -> AgentPatchOperationResult:
    return _result(operation, valid=False, code=code, message=message)


def _model_error(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return str(exc)
    first = errors[0]
    loc = ".".join(str(part) for part in first.get("loc", []))
    message = first.get("msg", "Invalid payload")
    return f"{loc}: {message}" if loc else str(message)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _timestamp_matches(current: datetime | None, expected: datetime | None) -> bool:
    if current is None or expected is None:
        return False
    return _utc_naive(current) == _utc_naive(expected)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _unknown_fields(entity: str, fields: dict[str, Any]) -> list[str]:
    allowed = ENTITY_FIELDS.get(entity, set())
    return sorted(set(fields) - allowed)


def _validate_operation_shape(
    operation: AgentPatchOperation,
) -> AgentPatchOperationResult | None:
    if operation.op not in VALID_OPS:
        return _invalid(operation, "OP_NOT_ALLOWED", "Only create and update are allowed")
    if operation.entity not in VALID_ENTITIES:
        return _invalid(
            operation,
            "ENTITY_NOT_ALLOWED",
            "Only project, solution, and subcomponent are allowed",
        )
    if not operation.fields:
        return _invalid(operation, "FIELDS_REQUIRED", "fields must not be empty")
    unknown = _unknown_fields(operation.entity, operation.fields)
    if unknown:
        return _invalid(
            operation,
            "FIELD_NOT_ALLOWED",
            f"Fields are not writable for {operation.entity}: {', '.join(unknown)}",
        )
    if operation.op == "update":
        if not operation.id:
            return _invalid(operation, "ID_REQUIRED", "update requires id")
        if not operation.if_updated_at:
            return _invalid(
                operation,
                "IF_UPDATED_AT_REQUIRED",
                "update requires if_updated_at",
            )
    if operation.op == "create" and operation.entity == "solution" and not operation.project_id:
        return _invalid(
            operation,
            "PROJECT_ID_REQUIRED",
            "create solution requires project_id",
        )
    if (
        operation.op == "create"
        and operation.entity == "subcomponent"
        and not operation.solution_id
    ):
        return _invalid(
            operation,
            "SOLUTION_ID_REQUIRED",
            "create subcomponent requires solution_id",
        )
    return None


def _validate_project(
    session: Session,
    space_ctx: SpaceContext,
    operation: AgentPatchOperation,
) -> AgentPatchOperationResult:
    try:
        if operation.op == "create":
            payload = ProjectCreate(**operation.fields)
            if payload.program_id:
                _ensure_program_exists(session, payload.program_id, space_ctx)
            project_name = normalize_str(payload.project_name)
            if not project_name:
                return _invalid(
                    operation, "PROJECT_NAME_REQUIRED", "project_name is required"
                )
            conflict = _active_project_name_conflict_query(
                session,
                project_name=project_name,
                space_id=space_ctx.space_id,
            ).first()
            if conflict:
                return _invalid(
                    operation,
                    "PROJECT_NAME_CONFLICT",
                    "Project name already exists",
                )
            return _result(operation, valid=True)

        payload = ProjectUpdate(**operation.fields)
        project = (
            _project_query(session, space_ctx)
            .filter(Project.project_id == operation.id)
            .first()
        )
        if not project:
            return _invalid(operation, "PROJECT_NOT_FOUND", "Project not found")
        if not _timestamp_matches(project.updated_at, operation.if_updated_at):
            return _invalid(
                operation,
                "STALE_ENTITY",
                "Project has changed since if_updated_at",
            )
        update_data = payload.model_dump(exclude_unset=True)
        if "program_id" in update_data:
            _ensure_program_exists(session, update_data["program_id"], space_ctx)
        if "project_name" in update_data:
            project_name = normalize_str(update_data["project_name"])
            if not project_name:
                return _invalid(
                    operation, "PROJECT_NAME_REQUIRED", "project_name is required"
                )
            conflict = (
                _project_query(session, space_ctx)
                .filter(Project.project_name == project_name)
                .filter(Project.project_id != project.project_id)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "PROJECT_NAME_CONFLICT",
                    "Project name already exists",
                )
        return _result(operation, valid=True, entity_id=project.project_id)
    except ValidationError as exc:
        return _invalid(operation, "VALIDATION_ERROR", _model_error(exc))


def _validate_solution(
    session: Session,
    space_ctx: SpaceContext,
    operation: AgentPatchOperation,
) -> AgentPatchOperationResult:
    try:
        if operation.op == "create":
            payload = SolutionCreate(**operation.fields)
            project = (
                _project_query(session, space_ctx)
                .filter(Project.project_id == operation.project_id)
                .first()
            )
            if not project:
                return _invalid(operation, "PROJECT_NOT_FOUND", "Project not found")
            solution_name = normalize_str(payload.solution_name)
            if not solution_name:
                return _invalid(
                    operation, "SOLUTION_NAME_REQUIRED", "solution_name is required"
                )
            version = normalize_str(payload.version) or "0.1.0"
            conflict = (
                _solution_query(session, space_ctx)
                .filter(Solution.project_id == project.project_id)
                .filter(Solution.solution_name == solution_name)
                .filter(Solution.version == version)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "SOLUTION_CONFLICT",
                    "Solution name and version already exist for this project",
                )
            if payload.github_repo_url is not None:
                normalize_solution_repo_url(payload.github_repo_url)
            if payload.current_phase:
                phase = (
                    session.query(Phase)
                    .filter(Phase.phase_id == payload.current_phase)
                    .first()
                )
                if not phase:
                    return _invalid(
                        operation,
                        "CURRENT_PHASE_INVALID",
                        f"current_phase '{payload.current_phase}' does not exist",
                    )
            return _result(operation, valid=True)

        payload = SolutionUpdate(**operation.fields)
        solution = (
            _solution_query(session, space_ctx)
            .filter(Solution.solution_id == operation.id)
            .first()
        )
        if not solution:
            return _invalid(operation, "SOLUTION_NOT_FOUND", "Solution not found")
        if not _timestamp_matches(solution.updated_at, operation.if_updated_at):
            return _invalid(
                operation,
                "STALE_ENTITY",
                "Solution has changed since if_updated_at",
            )
        update_data = payload.model_dump(exclude_unset=True)
        if "github_repo_url" in update_data:
            normalize_solution_repo_url(update_data["github_repo_url"])
        if "current_phase" in update_data:
            try:
                _validate_current_phase(
                    session, solution.solution_id, update_data["current_phase"]
                )
            except HTTPException as exc:
                return _invalid(operation, "CURRENT_PHASE_INVALID", str(exc.detail))
        next_name = normalize_str(update_data.get("solution_name")) or solution.solution_name
        next_version = normalize_str(update_data.get("version")) or solution.version
        if "solution_name" in update_data and not next_name:
            return _invalid(
                operation, "SOLUTION_NAME_REQUIRED", "solution_name is required"
            )
        if "version" in update_data and not next_version:
            return _invalid(operation, "VERSION_REQUIRED", "version is required")
        if "solution_name" in update_data or "version" in update_data:
            conflict = (
                _solution_query(session, space_ctx)
                .filter(Solution.project_id == solution.project_id)
                .filter(Solution.solution_name == next_name)
                .filter(Solution.version == next_version)
                .filter(Solution.solution_id != solution.solution_id)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "SOLUTION_CONFLICT",
                    "Solution name and version already exist for this project",
                )
        return _result(operation, valid=True, entity_id=solution.solution_id)
    except ValueError as exc:
        return _invalid(operation, "VALIDATION_ERROR", str(exc))
    except ValidationError as exc:
        return _invalid(operation, "VALIDATION_ERROR", _model_error(exc))


def _validate_subcomponent(
    session: Session,
    space_ctx: SpaceContext,
    operation: AgentPatchOperation,
) -> AgentPatchOperationResult:
    try:
        if operation.op == "create":
            payload = SubcomponentCreate(**operation.fields)
            solution = (
                _subcomponent_solution_query(session, space_ctx)
                .filter(Solution.solution_id == operation.solution_id)
                .first()
            )
            if not solution:
                return _invalid(operation, "SOLUTION_NOT_FOUND", "Solution not found")
            name = normalize_str(payload.subcomponent_name)
            if not name:
                return _invalid(
                    operation,
                    "SUBCOMPONENT_NAME_REQUIRED",
                    "subcomponent_name is required",
                )
            conflict = (
                _subcomponent_query(session, space_ctx)
                .filter(Subcomponent.solution_id == solution.solution_id)
                .filter(Subcomponent.subcomponent_name == name)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "SUBCOMPONENT_CONFLICT",
                    "Subcomponent name already exists in this solution",
                )
            if payload.github_repo_url is not None:
                normalize_subcomponent_repo_url(payload.github_repo_url)
            return _result(operation, valid=True)

        payload = SubcomponentUpdate(**operation.fields)
        subcomponent = (
            _subcomponent_query(session, space_ctx)
            .filter(Subcomponent.subcomponent_id == operation.id)
            .first()
        )
        if not subcomponent:
            return _invalid(
                operation, "SUBCOMPONENT_NOT_FOUND", "Subcomponent not found"
            )
        if not _timestamp_matches(subcomponent.updated_at, operation.if_updated_at):
            return _invalid(
                operation,
                "STALE_ENTITY",
                "Subcomponent has changed since if_updated_at",
            )
        update_data = payload.model_dump(exclude_unset=True)
        if "github_repo_url" in update_data:
            normalize_subcomponent_repo_url(update_data["github_repo_url"])
        if "subcomponent_name" in update_data:
            name = normalize_str(update_data["subcomponent_name"])
            if not name:
                return _invalid(
                    operation,
                    "SUBCOMPONENT_NAME_REQUIRED",
                    "subcomponent_name is required",
                )
            conflict = (
                _subcomponent_query(session, space_ctx)
                .filter(Subcomponent.solution_id == subcomponent.solution_id)
                .filter(Subcomponent.subcomponent_name == name)
                .filter(Subcomponent.subcomponent_id != subcomponent.subcomponent_id)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "SUBCOMPONENT_CONFLICT",
                    "Subcomponent name already exists in this solution",
                )
        return _result(operation, valid=True, entity_id=subcomponent.subcomponent_id)
    except ValueError as exc:
        return _invalid(operation, "VALIDATION_ERROR", str(exc))
    except ValidationError as exc:
        return _invalid(operation, "VALIDATION_ERROR", _model_error(exc))


def validate_patch_plan(
    session: Session,
    space_ctx: SpaceContext,
    payload: AgentPatchRequest,
    *,
    for_apply: bool = False,
) -> AgentPatchResponse:
    results: list[AgentPatchOperationResult] = []
    seen_ids: set[str] = set()
    if for_apply:
        if payload.dry_run is not False:
            synthetic = payload.operations[0]
            results.append(
                _invalid(
                    synthetic,
                    "DRY_RUN_FALSE_REQUIRED",
                    "apply requires dry_run=false",
                )
            )
        if not normalize_str(payload.reason):
            synthetic = payload.operations[0]
            results.append(
                _invalid(synthetic, "REASON_REQUIRED", "apply requires reason")
            )
        if not normalize_str(payload.idempotency_key):
            synthetic = payload.operations[0]
            results.append(
                _invalid(
                    synthetic,
                    "IDEMPOTENCY_KEY_REQUIRED",
                    "apply requires idempotency_key",
                )
            )

    for operation in payload.operations:
        if operation.client_operation_id in seen_ids:
            results.append(
                _invalid(
                    operation,
                    "DUPLICATE_OPERATION_ID",
                    "client_operation_id values must be unique",
                )
            )
            continue
        seen_ids.add(operation.client_operation_id)
        shape_error = _validate_operation_shape(operation)
        if shape_error:
            results.append(shape_error)
            continue
        if operation.entity == "project":
            results.append(_validate_project(session, space_ctx, operation))
        elif operation.entity == "solution":
            results.append(_validate_solution(session, space_ctx, operation))
        elif operation.entity == "subcomponent":
            results.append(_validate_subcomponent(session, space_ctx, operation))

    valid = all(result.valid for result in results)
    return AgentPatchResponse(
        valid=valid,
        applied=False,
        dry_run=payload.dry_run,
        operation_count=len(payload.operations),
        results=results,
    )


def _apply_project(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    operation: AgentPatchOperation,
) -> tuple[str, datetime]:
    if operation.op == "create":
        payload = ProjectCreate(**operation.fields)
        program = (
            _ensure_program_exists(session, payload.program_id, space_ctx)
            if payload.program_id
            else _default_program(session, space_ctx)
        )
        sponsor, sponsor_user_soeid = _resolve_project_sponsor(
            payload.sponsor,
            payload.sponsor_user_soeid,
            current_user,
        )
        project = Project(
            space_id=space_ctx.space_id,
            program_id=program.program_id,
            project_name=normalize_str(payload.project_name),
            status=payload.status,
            description=payload.description,
            success_criteria=payload.success_criteria,
            sponsor=sponsor,
            sponsor_user_soeid=sponsor_user_soeid,
            strategic_objective=payload.strategic_objective,
            priority=payload.priority if payload.priority is not None else 3,
        )
        session.add(project)
        session.flush()
        safe_log_changes(
            session,
            entity_type="project",
            entity_id=project.project_id,
            user_id=current_user.user_id,
            action="create",
            space_id=space_ctx.space_id,
            changes=_project_create_changes(project),
        )
        return project.project_id, project.updated_at

    payload = ProjectUpdate(**operation.fields)
    project = (
        _project_query(session, space_ctx)
        .filter(Project.project_id == operation.id)
        .first()
    )
    update_data = payload.model_dump(exclude_unset=True)
    if "program_id" in update_data:
        program = _ensure_program_exists(session, update_data["program_id"], space_ctx)
        update_data["program_id"] = program.program_id
    if "project_name" in update_data:
        update_data["project_name"] = normalize_str(update_data["project_name"])
    before = {field: getattr(project, field) for field in update_data}
    for field, value in update_data.items():
        setattr(project, field, value)
    project.updated_at = _now()
    session.add(project)
    if update_data:
        safe_log_changes(
            session,
            entity_type="project",
            entity_id=project.project_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes=_project_change_set(project, before, update_data.keys()),
        )
    return project.project_id, project.updated_at


def _apply_solution(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    operation: AgentPatchOperation,
) -> tuple[str, datetime]:
    if operation.op == "create":
        payload = SolutionCreate(**operation.fields)
        owner, owner_user_soeid = _resolve_solution_owner(
            payload.owner,
            payload.owner_user_soeid,
            current_user,
        )
        assignee, assignee_user_soeid = _resolve_solution_assignee(
            payload.assignee,
            payload.assignee_user_soeid,
            owner=owner,
            owner_user_soeid=owner_user_soeid,
            current_user=current_user,
        )
        now = _now()
        status_value = payload.status or SolutionStatus.not_started
        solution = Solution(
            space_id=space_ctx.space_id,
            project_id=operation.project_id,
            solution_name=normalize_str(payload.solution_name),
            version=normalize_str(payload.version) or "0.1.0",
            status=status_value,
            rag_status=payload.rag_status,
            rag_reason=normalize_str(payload.rag_reason) or None,
            priority=parse_priority(payload.priority, default=3),
            due_date=payload.due_date,
            planned_start_date=payload.planned_start_date,
            current_phase=normalize_str(payload.current_phase) or None,
            description=payload.description,
            success_criteria=payload.success_criteria,
            problem_statement=payload.problem_statement,
            github_repo_url=normalize_solution_repo_url(payload.github_repo_url),
            impact_confidence=payload.impact_confidence,
            owner=owner,
            owner_user_soeid=owner_user_soeid,
            assignee=assignee or "",
            assignee_user_soeid=assignee_user_soeid,
            approver=payload.approver,
            approver_user_soeid=payload.approver_user_soeid,
            key_stakeholder=payload.key_stakeholder,
            blockers=payload.blockers,
            risks=payload.risks,
            rag_confidence=payload.rag_confidence,
            completed_at=now if status_value == SolutionStatus.complete else None,
            created_at=now,
            updated_at=now,
            capacity_hours=payload.capacity_hours or 0,
        )
        session.add(solution)
        session.flush()
        log_changes(
            session,
            entity_type="solution",
            entity_id=solution.solution_id,
            user_id=current_user.user_id,
            action="create",
            space_id=space_ctx.space_id,
            changes={
                "solution_name": (None, solution.solution_name),
                "version": (None, solution.version),
                "status": (None, solution.status),
                "rag_status": (None, solution.rag_status),
                "priority": (None, solution.priority),
            },
        )
        _run_enable_all_phases(session, solution.solution_id)
        return solution.solution_id, solution.updated_at

    payload = SolutionUpdate(**operation.fields)
    solution = (
        _solution_query(session, space_ctx)
        .filter(Solution.solution_id == operation.id)
        .first()
    )
    update_data = payload.model_dump(exclude_unset=True)
    rag_updates = {
        k: update_data.pop(k)
        for k in list(update_data.keys())
        if k in {"rag_status", "rag_reason"}
    }
    if "solution_name" in update_data:
        update_data["solution_name"] = normalize_str(update_data["solution_name"])
    if "version" in update_data:
        update_data["version"] = normalize_str(update_data["version"])
    if "priority" in update_data:
        update_data["priority"] = parse_priority(update_data["priority"], default=3)
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "github_repo_url" in update_data:
        update_data["github_repo_url"] = normalize_solution_repo_url(
            update_data["github_repo_url"]
        )
    if "current_phase" in update_data:
        update_data["current_phase"] = normalize_str(update_data["current_phase"]) or None
    fields_to_compare = set(update_data) | {"rag_status", "rag_reason"}
    if "status" in update_data:
        fields_to_compare.update({"completed_at", "current_phase"})
    before = {field: getattr(solution, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(solution, field, value)
    solution.updated_at = _now()
    if "status" in update_data:
        _apply_solution_completion_state(
            session,
            solution,
            next_status=update_data["status"],
            now=solution.updated_at,
        )
    if "rag_status" in rag_updates and rag_updates.get("rag_status") is not None:
        solution.rag_status = rag_updates["rag_status"]
    if "rag_reason" in rag_updates:
        solution.rag_reason = normalize_str(rag_updates["rag_reason"]) or None
    session.add(solution)
    log_changes(
        session,
        entity_type="solution",
        entity_id=solution.solution_id,
        user_id=current_user.user_id,
        action="update",
        space_id=space_ctx.space_id,
        changes={
            field: (before.get(field), getattr(solution, field))
            for field in fields_to_compare
        },
    )
    return solution.solution_id, solution.updated_at


def _apply_subcomponent(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    operation: AgentPatchOperation,
) -> tuple[str, datetime]:
    if operation.op == "create":
        payload = SubcomponentCreate(**operation.fields)
        solution = _ensure_solution(session, operation.solution_id, space_ctx)
        assignee, assignee_user_soeid = _resolve_subcomponent_assignee(
            payload.assignee,
            payload.assignee_user_soeid,
            current_user,
        )
        now = _now()
        status_value = payload.status or SubcomponentStatus.to_do
        subcomponent = Subcomponent(
            space_id=space_ctx.space_id,
            project_id=solution.project_id,
            solution_id=solution.solution_id,
            subcomponent_name=normalize_str(payload.subcomponent_name),
            status=status_value,
            priority=payload.priority,
            due_date=payload.due_date,
            completed_at=now if status_value == SubcomponentStatus.complete else None,
            assignee=assignee,
            assignee_user_soeid=assignee_user_soeid,
            github_repo_url=normalize_subcomponent_repo_url(payload.github_repo_url),
            estimate_hours=payload.estimate_hours,
            blocked=payload.blocked or False,
            blocker_note=payload.blocker_note if payload.blocked else None,
            done_criteria=payload.done_criteria,
            capacity_hours=payload.capacity_hours or 0,
            created_at=now,
            updated_at=now,
        )
        session.add(subcomponent)
        session.flush()
        log_changes(
            session,
            entity_type="subcomponent",
            entity_id=subcomponent.subcomponent_id,
            user_id=current_user.user_id,
            action="create",
            space_id=space_ctx.space_id,
            changes={
                "subcomponent_name": (None, subcomponent.subcomponent_name),
                "status": (None, subcomponent.status),
                "priority": (None, subcomponent.priority),
            },
        )
        return subcomponent.subcomponent_id, subcomponent.updated_at

    payload = SubcomponentUpdate(**operation.fields)
    subcomponent = (
        _subcomponent_query(session, space_ctx)
        .filter(Subcomponent.subcomponent_id == operation.id)
        .first()
    )
    update_data = payload.model_dump(exclude_unset=True)
    if "subcomponent_name" in update_data:
        update_data["subcomponent_name"] = normalize_str(
            update_data["subcomponent_name"]
        )
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "blocked" in update_data and update_data["blocked"] is None:
        update_data["blocked"] = False
    if update_data.get("blocked") is False:
        update_data["blocker_note"] = None
    if "github_repo_url" in update_data:
        update_data["github_repo_url"] = normalize_subcomponent_repo_url(
            update_data["github_repo_url"]
        )
    fields_to_compare = set(update_data)
    if "status" in update_data:
        fields_to_compare.add("completed_at")
    before = {field: getattr(subcomponent, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(subcomponent, field, value)
    if "status" in update_data:
        _apply_subcomponent_completion_state(
            subcomponent,
            next_status=update_data["status"],
            now=_now(),
        )
    subcomponent.updated_at = _now()
    session.add(subcomponent)
    log_changes(
        session,
        entity_type="subcomponent",
        entity_id=subcomponent.subcomponent_id,
        user_id=current_user.user_id,
        action="update",
        space_id=space_ctx.space_id,
        changes={
            field: (before.get(field), getattr(subcomponent, field))
            for field in fields_to_compare
        },
    )
    return subcomponent.subcomponent_id, subcomponent.updated_at


def apply_patch_plan(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    payload: AgentPatchRequest,
) -> AgentPatchResponse:
    validation = validate_patch_plan(session, space_ctx, payload, for_apply=True)
    if not validation.valid:
        return validation

    results: list[AgentPatchOperationResult] = []
    publish_entities: set[str] = set()
    try:
        for operation in payload.operations:
            if operation.entity == "project":
                entity_id, updated_at = _apply_project(
                    session, space_ctx, current_user, operation
                )
            elif operation.entity == "solution":
                entity_id, updated_at = _apply_solution(
                    session, space_ctx, current_user, operation
                )
            else:
                entity_id, updated_at = _apply_subcomponent(
                    session, space_ctx, current_user, operation
                )
            publish_entities.add(operation.entity)
            results.append(
                _result(
                    operation,
                    valid=True,
                    applied=True,
                    entity_id=entity_id,
                    updated_at=updated_at,
                )
            )
        session.commit()
    except Exception as exc:
        session.rollback()
        first = payload.operations[0]
        return AgentPatchResponse(
            valid=False,
            applied=False,
            dry_run=payload.dry_run,
            operation_count=len(payload.operations),
            results=[
                _invalid(
                    first,
                    "APPLY_FAILED",
                    "Patch application failed due to a data conflict"
                    if _is_project_name_conflict_integrity_error(exc)
                    else str(exc),
                )
            ],
        )

    for entity in publish_entities:
        publish_space_mutation(
            space_ctx.space_id,
            PUBLISH_KEYS[entity],
            broadcast_channel=PUBLISH_KEYS[entity][0],
        )

    return AgentPatchResponse(
        valid=True,
        applied=True,
        dry_run=payload.dry_run,
        operation_count=len(payload.operations),
        results=results,
    )
