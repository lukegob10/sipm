from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Phase, Program, Project, Solution, Task, User
from ..schemas import ProgramCreate, ProgramUpdate, ProjectCreate, ProjectUpdate
from ..schemas import SolutionCreate, SolutionUpdate
from ..schemas import TaskCreate, TaskUpdate
from ..schemas.agent import (
    AgentPatchOperation,
    AgentPatchOperationResult,
    AgentPatchRequest,
    AgentPatchResponse,
)
from ..services.audit_log import log_changes, safe_log_changes
from ..services.mutations import publish_space_mutation
from ..services.programs import program_query as _program_query
from ..services.spaces import SpaceContext
from ..services.work_items import (
    active_project_name_conflict_query as _active_project_name_conflict_query,
    apply_solution_completion_state as _apply_solution_completion_state,
    apply_task_completion_state as _apply_task_completion_state,
    default_program as _default_program,
    ensure_program_exists as _ensure_program_exists,
    ensure_solution as _ensure_solution,
    is_project_name_conflict_integrity_error as _is_project_name_conflict_integrity_error,
    normalize_github_repo_url as normalize_solution_repo_url,
    normalize_github_repo_url as normalize_task_repo_url,
    project_change_set as _project_change_set,
    project_create_changes as _project_create_changes,
    project_query as _project_query,
    resolve_project_sponsor as _resolve_project_sponsor,
    resolve_solution_assignee as _resolve_solution_assignee,
    resolve_solution_owner as _resolve_solution_owner,
    resolve_task_assignee as _resolve_task_assignee,
    run_enable_all_phases as _run_enable_all_phases,
    solution_query as _solution_query,
    task_query as _task_query,
    task_solution_query as _task_solution_query,
    validate_current_phase as _validate_current_phase,
)
from ..utils import normalize_str, parse_priority
from ..utils.enums import SolutionStatus, TaskStatus

VALID_OPS = {"create", "update"}
VALID_ENTITIES = {"program", "project", "solution", "task"}
PROGRAM_FIELDS = set(ProgramCreate.model_fields)
PROJECT_FIELDS = set(ProjectCreate.model_fields)
SOLUTION_FIELDS = set(SolutionCreate.model_fields)
TASK_FIELDS = set(TaskCreate.model_fields)
ENTITY_FIELDS = {
    "program": PROGRAM_FIELDS,
    "project": PROJECT_FIELDS,
    "solution": SOLUTION_FIELDS,
    "task": TASK_FIELDS,
}
PUBLISH_KEYS = {
    "program": ("programs",),
    "project": ("projects",),
    "solution": ("solutions",),
    "task": ("tasks",),
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


def _is_program_name_conflict_integrity_error(exc: Exception) -> bool:
    if not isinstance(exc, IntegrityError):
        return False
    text = " ".join(
        [
            str(exc),
            str(getattr(exc, "orig", "")),
            str(getattr(exc, "statement", "")),
        ]
    ).lower()
    if "uix_program_space_name" in text:
        return True
    has_unique_marker = any(
        marker in text
        for marker in (
            "ora-03301",
            "ora-00001",
            "unique constraint",
            "unique constraint failed",
        )
    )
    return has_unique_marker and (
        "program_name" in text or "tb_ta_pm_programs" in text
    )


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
            "Only program, project, solution, and task are allowed",
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
        and operation.entity == "task"
        and not operation.solution_id
    ):
        return _invalid(
            operation,
            "SOLUTION_ID_REQUIRED",
            "create task requires solution_id",
        )
    return None


def _validate_program(
    session: Session,
    space_ctx: SpaceContext,
    operation: AgentPatchOperation,
) -> AgentPatchOperationResult:
    try:
        if operation.op == "create":
            payload = ProgramCreate(**operation.fields)
            program_name = normalize_str(payload.program_name)
            if not program_name:
                return _invalid(
                    operation, "PROGRAM_NAME_REQUIRED", "program_name is required"
                )
            conflict = (
                _program_query(session, space_ctx)
                .filter(Program.program_name == program_name)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "PROGRAM_NAME_CONFLICT",
                    "Program name already exists",
                )
            return _result(operation, valid=True)

        payload = ProgramUpdate(**operation.fields)
        program = (
            _program_query(session, space_ctx)
            .filter(Program.program_id == operation.id)
            .first()
        )
        if not program:
            return _invalid(operation, "PROGRAM_NOT_FOUND", "Program not found")
        if not _timestamp_matches(program.updated_at, operation.if_updated_at):
            return _invalid(
                operation,
                "STALE_ENTITY",
                "Program has changed since if_updated_at",
            )
        update_data = payload.model_dump(exclude_unset=True)
        if "program_name" in update_data:
            program_name = normalize_str(update_data["program_name"])
            if not program_name:
                return _invalid(
                    operation, "PROGRAM_NAME_REQUIRED", "program_name is required"
                )
            conflict = (
                _program_query(session, space_ctx)
                .filter(Program.program_name == program_name)
                .filter(Program.program_id != program.program_id)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "PROGRAM_NAME_CONFLICT",
                    "Program name already exists",
                )
        return _result(operation, valid=True, entity_id=program.program_id)
    except ValidationError as exc:
        return _invalid(operation, "VALIDATION_ERROR", _model_error(exc))


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


def _validate_task(
    session: Session,
    space_ctx: SpaceContext,
    operation: AgentPatchOperation,
) -> AgentPatchOperationResult:
    try:
        if operation.op == "create":
            payload = TaskCreate(**operation.fields)
            solution = (
                _task_solution_query(session, space_ctx)
                .filter(Solution.solution_id == operation.solution_id)
                .first()
            )
            if not solution:
                return _invalid(operation, "SOLUTION_NOT_FOUND", "Solution not found")
            name = normalize_str(payload.task_name)
            if not name:
                return _invalid(
                    operation,
                    "TASK_NAME_REQUIRED",
                    "task_name is required",
                )
            conflict = (
                _task_query(session, space_ctx)
                .filter(Task.solution_id == solution.solution_id)
                .filter(Task.task_name == name)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "TASK_CONFLICT",
                    "Task name already exists in this solution",
                )
            if payload.github_repo_url is not None:
                normalize_task_repo_url(payload.github_repo_url)
            return _result(operation, valid=True)

        payload = TaskUpdate(**operation.fields)
        task = (
            _task_query(session, space_ctx)
            .filter(Task.task_id == operation.id)
            .first()
        )
        if not task:
            return _invalid(
                operation, "TASK_NOT_FOUND", "Task not found"
            )
        if not _timestamp_matches(task.updated_at, operation.if_updated_at):
            return _invalid(
                operation,
                "STALE_ENTITY",
                "Task has changed since if_updated_at",
            )
        update_data = payload.model_dump(exclude_unset=True)
        if "github_repo_url" in update_data:
            normalize_task_repo_url(update_data["github_repo_url"])
        if "task_name" in update_data:
            name = normalize_str(update_data["task_name"])
            if not name:
                return _invalid(
                    operation,
                    "TASK_NAME_REQUIRED",
                    "task_name is required",
                )
            conflict = (
                _task_query(session, space_ctx)
                .filter(Task.solution_id == task.solution_id)
                .filter(Task.task_name == name)
                .filter(Task.task_id != task.task_id)
                .first()
            )
            if conflict:
                return _invalid(
                    operation,
                    "TASK_CONFLICT",
                    "Task name already exists in this solution",
                )
        return _result(operation, valid=True, entity_id=task.task_id)
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
        if operation.entity == "program":
            results.append(_validate_program(session, space_ctx, operation))
        elif operation.entity == "project":
            results.append(_validate_project(session, space_ctx, operation))
        elif operation.entity == "solution":
            results.append(_validate_solution(session, space_ctx, operation))
        elif operation.entity == "task":
            results.append(_validate_task(session, space_ctx, operation))

    valid = all(result.valid for result in results)
    return AgentPatchResponse(
        valid=valid,
        applied=False,
        dry_run=payload.dry_run,
        operation_count=len(payload.operations),
        results=results,
    )


def _apply_program(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    operation: AgentPatchOperation,
) -> tuple[str, datetime]:
    if operation.op == "create":
        payload = ProgramCreate(**operation.fields)
        now = _now()
        program = Program(
            space_id=space_ctx.space_id,
            program_name=normalize_str(payload.program_name),
            description=payload.description,
            created_at=now,
            updated_at=now,
        )
        session.add(program)
        session.flush()
        safe_log_changes(
            session,
            entity_type="program",
            entity_id=program.program_id,
            user_id=current_user.user_id,
            action="create",
            space_id=space_ctx.space_id,
            changes={
                "program_name": (None, program.program_name),
                "description": (None, program.description),
            },
        )
        return program.program_id, program.updated_at

    payload = ProgramUpdate(**operation.fields)
    program = (
        _program_query(session, space_ctx)
        .filter(Program.program_id == operation.id)
        .first()
    )
    update_data = payload.model_dump(exclude_unset=True)
    if "program_name" in update_data:
        update_data["program_name"] = normalize_str(update_data["program_name"])
    before = {field: getattr(program, field) for field in update_data}
    for field, value in update_data.items():
        setattr(program, field, value)
    program.updated_at = _now()
    session.add(program)
    if update_data:
        safe_log_changes(
            session,
            entity_type="program",
            entity_id=program.program_id,
            user_id=current_user.user_id,
            action="update",
            space_id=space_ctx.space_id,
            changes={
                field: (before.get(field), getattr(program, field))
                for field in update_data
            },
        )
    return program.program_id, program.updated_at


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
            escalation=normalize_str(payload.escalation) or None,
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
    if "escalation" in update_data:
        update_data["escalation"] = normalize_str(update_data["escalation"]) or None
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


def _apply_task(
    session: Session,
    space_ctx: SpaceContext,
    current_user: User,
    operation: AgentPatchOperation,
) -> tuple[str, datetime]:
    if operation.op == "create":
        payload = TaskCreate(**operation.fields)
        solution = _ensure_solution(session, operation.solution_id, space_ctx)
        assignee, assignee_user_soeid = _resolve_task_assignee(
            payload.assignee,
            payload.assignee_user_soeid,
            current_user,
        )
        now = _now()
        status_value = payload.status or TaskStatus.to_do
        task = Task(
            space_id=space_ctx.space_id,
            project_id=solution.project_id,
            solution_id=solution.solution_id,
            task_name=normalize_str(payload.task_name),
            status=status_value,
            priority=payload.priority,
            due_date=payload.due_date,
            completed_at=now if status_value == TaskStatus.complete else None,
            assignee=assignee,
            assignee_user_soeid=assignee_user_soeid,
            github_repo_url=normalize_task_repo_url(payload.github_repo_url),
            estimate_hours=payload.estimate_hours,
            blocked=payload.blocked or False,
            blocker_note=payload.blocker_note if payload.blocked else None,
            done_criteria=payload.done_criteria,
            capacity_hours=payload.capacity_hours or 0,
            created_at=now,
            updated_at=now,
        )
        session.add(task)
        session.flush()
        log_changes(
            session,
            entity_type="task",
            entity_id=task.task_id,
            user_id=current_user.user_id,
            action="create",
            space_id=space_ctx.space_id,
            changes={
                "task_name": (None, task.task_name),
                "status": (None, task.status),
                "priority": (None, task.priority),
            },
        )
        return task.task_id, task.updated_at

    payload = TaskUpdate(**operation.fields)
    task = (
        _task_query(session, space_ctx)
        .filter(Task.task_id == operation.id)
        .first()
    )
    update_data = payload.model_dump(exclude_unset=True)
    if "task_name" in update_data:
        update_data["task_name"] = normalize_str(
            update_data["task_name"]
        )
    if "capacity_hours" in update_data and update_data["capacity_hours"] is None:
        update_data["capacity_hours"] = 0
    if "blocked" in update_data and update_data["blocked"] is None:
        update_data["blocked"] = False
    if update_data.get("blocked") is False:
        update_data["blocker_note"] = None
    if "github_repo_url" in update_data:
        update_data["github_repo_url"] = normalize_task_repo_url(
            update_data["github_repo_url"]
        )
    fields_to_compare = set(update_data)
    if "status" in update_data:
        fields_to_compare.add("completed_at")
    before = {field: getattr(task, field) for field in fields_to_compare}
    for field, value in update_data.items():
        setattr(task, field, value)
    if "status" in update_data:
        _apply_task_completion_state(
            task,
            next_status=update_data["status"],
            now=_now(),
        )
    task.updated_at = _now()
    session.add(task)
    log_changes(
        session,
        entity_type="task",
        entity_id=task.task_id,
        user_id=current_user.user_id,
        action="update",
        space_id=space_ctx.space_id,
        changes={
            field: (before.get(field), getattr(task, field))
            for field in fields_to_compare
        },
    )
    return task.task_id, task.updated_at


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
    publish_keys: set[str] = set()
    try:
        for operation in payload.operations:
            if operation.entity == "program":
                entity_id, updated_at = _apply_program(
                    session, space_ctx, current_user, operation
                )
            elif operation.entity == "project":
                entity_id, updated_at = _apply_project(
                    session, space_ctx, current_user, operation
                )
            elif operation.entity == "solution":
                entity_id, updated_at = _apply_solution(
                    session, space_ctx, current_user, operation
                )
            else:
                entity_id, updated_at = _apply_task(
                    session, space_ctx, current_user, operation
                )
            publish_keys.update(PUBLISH_KEYS[operation.entity])
            if (
                operation.entity == "program"
                and operation.op == "update"
                and "program_name" in operation.fields
            ):
                publish_keys.add("projects")
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
                    or _is_program_name_conflict_integrity_error(exc)
                    else str(exc),
                )
            ],
        )

    for key in sorted(publish_keys):
        publish_space_mutation(
            space_ctx.space_id,
            [key],
            broadcast_channel=key,
        )

    return AgentPatchResponse(
        valid=True,
        applied=True,
        dry_run=payload.dry_run,
        operation_count=len(payload.operations),
        results=results,
    )
