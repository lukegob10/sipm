from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_non_agent_write, require_space_role
from ...models import Program, Project, User
from ...services.audit_log import safe_log_changes
from ...services.spaces import SpaceContext
from ...services.work_items import lock_work_space
from ...utils import normalize_status, normalize_str, parse_priority, read_csv, read_text_value
from ...utils.enums import ProjectStatus
from .common import (
    _default_program,
    _deleted_project_name,
    _ensure_program_exists,
    _project_change_set,
    _project_create_changes,
    _project_query,
    _publish_project_mutation,
    _resolve_project_owner,
    _resolve_project_sponsor,
)

router = APIRouter()
logger = logging.getLogger(__name__)
_PROJECT_IMPORT_UPDATE_FIELDS = (
    "program_id",
    "function",
    "area",
    "status",
    "description",
    "success_criteria",
    "sponsor",
    "sponsor_user_soeid",
    "owner",
    "owner_user_soeid",
    "strategic_objective",
    "priority",
)
_PROJECT_EXPORT_FIELDNAMES = [
    "program_id",
    "program_name",
    "project_name",
    "function",
    "area",
    "status",
    "description",
    "success_criteria",
    "sponsor",
    "sponsor_user_soeid",
    "owner",
    "owner_user_soeid",
    "strategic_objective",
    "priority",
]


def _resolve_import_program(
    session: Session,
    space_ctx: SpaceContext,
    *,
    program_id: object | None,
    program_name: object | None,
) -> Program:
    raw_program_id = normalize_str(program_id)
    if raw_program_id:
        return _ensure_program_exists(session, raw_program_id, space_ctx)
    raw_program_name = normalize_str(program_name)
    if raw_program_name:
        program = (
            session.query(Program)
            .filter(Program.deleted_at.is_(None))
            .filter(Program.space_id == space_ctx.space_id)
            .filter(Program.program_name == raw_program_name)
            .first()
        )
        if not program:
            raise ValueError(f"program_name '{raw_program_name}' does not exist")
        return program
    return _default_program(session, space_ctx)


@router.post("/import")
def import_projects(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    dry_run: bool = False,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"created": 0, "updated": 0, "errors": errors, "total_rows": 0, "dry_run": dry_run}
    created = updated = 0
    seen = set()
    for idx, row in enumerate(rows, start=2):
        if None in row:
            errors.append(f"Row {idx}: too many columns for the CSV header")
            continue
        name = normalize_str(row.get("project_name"))
        project_function = normalize_str(row.get("function")) or None
        area = normalize_str(row.get("area")) or None
        oversized_field = next(
            (field for field, value in (("function", project_function), ("area", area)) if value and len(value) > 255),
            None,
        )
        if oversized_field:
            errors.append(f"Row {idx}: {oversized_field} must be 255 characters or fewer")
            continue
        sponsor_input = normalize_str(row.get("sponsor"))
        owner_input = normalize_str(row.get("owner"))
        if not name:
            errors.append(f"Row {idx}: project_name is required")
            continue
        if len(name) > 255:
            errors.append(f"Row {idx}: project_name must be 255 characters or fewer")
            continue
        key = name.lower()
        if key in seen:
            errors.append(f"Row {idx}: duplicate project_name '{name}' in CSV (strict-first policy)")
            continue
        seen.add(key)
        try:
            status_enum = normalize_status(
                row.get("status") or ProjectStatus.not_started.value, ProjectStatus
            )
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue

        description = normalize_str(row.get("description")) or None
        success_criteria = normalize_str(row.get("success_criteria")) or None
        strategic_objective = normalize_str(row.get("strategic_objective")) or None
        try:
            priority_val = parse_priority(row.get("priority"), default=3)
        except ValueError as exc:
            errors.append(f"Row {idx}: {exc}")
            continue
        sponsor_user_soeid = normalize_str(row.get("sponsor_user_soeid")) or None
        owner_user_soeid = normalize_str(row.get("owner_user_soeid")) or None
        oversized_person_field = next(
            (field for field, value in (("sponsor", sponsor_input), ("sponsor_user_soeid", sponsor_user_soeid),
                                        ("owner", owner_input), ("owner_user_soeid", owner_user_soeid))
             if value and len(value) > 255),
            None,
        )
        if oversized_person_field:
            errors.append(f"Row {idx}: {oversized_person_field} must be 255 characters or fewer")
            continue
        if not dry_run:
            try:
                lock_work_space(session, space_ctx, current_user)
            except HTTPException:
                if not (created or updated):
                    raise
                session.rollback()
                errors.append(f"Row {idx}: import stopped because access to the space changed")
                break
        try:
            program = _resolve_import_program(
                session,
                space_ctx,
                program_id=row.get("program_id"),
                program_name=row.get("program_name"),
            )
        except (ValueError, HTTPException) as exc:
            session.rollback()
            if isinstance(exc, HTTPException) and exc.status_code >= 500:
                logger.warning("Program resolution failed (%s)", type(exc).__name__)
                errors.append(f"Row {idx}: program could not be resolved")
            else:
                errors.append(f"Row {idx}: {exc}")
            continue
        except Exception as exc:
            session.rollback()
            logger.warning("Program resolution failed (%s)", type(exc).__name__)
            errors.append(f"Row {idx}: program could not be resolved")
            continue
        try:
            existing = _project_query(session, space_ctx).filter(Project.project_name == name).first()
            if existing:
                if dry_run:
                    updated += 1
                    continue
                if sponsor_input:
                    resolved_sponsor, resolved_sponsor_user_soeid = _resolve_project_sponsor(
                        sponsor_input,
                        sponsor_user_soeid,
                        current_user,
                    )
                else:
                    resolved_sponsor = existing.sponsor
                    resolved_sponsor_user_soeid = existing.sponsor_user_soeid
                if owner_input:
                    resolved_owner, resolved_owner_user_soeid = _resolve_project_owner(
                        owner_input,
                        owner_user_soeid,
                        current_user,
                    )
                else:
                    resolved_owner = existing.owner
                    resolved_owner_user_soeid = existing.owner_user_soeid
                before = {field: getattr(existing, field) for field in _PROJECT_IMPORT_UPDATE_FIELDS}
                existing.program_id = program.program_id
                existing.function = project_function
                existing.area = area
                existing.status = status_enum
                existing.description = description
                existing.success_criteria = success_criteria
                existing.sponsor = resolved_sponsor
                existing.sponsor_user_soeid = resolved_sponsor_user_soeid
                existing.owner = resolved_owner
                existing.owner_user_soeid = resolved_owner_user_soeid
                existing.strategic_objective = strategic_objective
                existing.priority = priority_val
                if not existing.space_id:
                    existing.space_id = space_ctx.space_id
                existing.updated_at = datetime.now(timezone.utc)
                session.add(existing)
                safe_log_changes(
                    session,
                    entity_type="project",
                    entity_id=existing.project_id,
                    user_id=current_user.user_id,
                    action="update",
                    space_id=space_ctx.space_id,
                    changes=_project_change_set(existing, before, _PROJECT_IMPORT_UPDATE_FIELDS),
                    request_id=None,
                )
            else:
                if dry_run:
                    _resolve_project_sponsor(
                        sponsor_input,
                        sponsor_user_soeid,
                        current_user,
                    )
                    _resolve_project_owner(owner_input, owner_user_soeid, current_user)
                    created += 1
                    continue
                resolved_sponsor, resolved_sponsor_user_soeid = _resolve_project_sponsor(
                    sponsor_input,
                    sponsor_user_soeid,
                    current_user,
                )
                resolved_owner, resolved_owner_user_soeid = _resolve_project_owner(
                    owner_input,
                    owner_user_soeid,
                    current_user,
                )
                deleted_conflicts = (
                    session.query(Project)
                    .filter(Project.deleted_at.is_not(None))
                    .filter(Project.space_id == space_ctx.space_id)
                    .filter(Project.project_name == name)
                    .all()
                )
                now = datetime.now(timezone.utc)
                for deleted in deleted_conflicts:
                    deleted.project_name = _deleted_project_name(
                        deleted.project_name,
                        deleted.project_id,
                        deleted.deleted_at or now,
                    )
                    deleted.updated_at = now
                    session.add(deleted)
                if deleted_conflicts:
                    session.flush()
                project = Project(
                    space_id=space_ctx.space_id,
                    program_id=program.program_id,
                    project_name=name,
                    function=project_function,
                    area=area,
                    status=status_enum,
                    description=description,
                    success_criteria=success_criteria,
                    sponsor=resolved_sponsor,
                    sponsor_user_soeid=resolved_sponsor_user_soeid,
                    owner=resolved_owner,
                    owner_user_soeid=resolved_owner_user_soeid,
                    strategic_objective=strategic_objective,
                    priority=priority_val,
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
                    request_id=None,
                )
            session.commit()
            if existing:
                updated += 1
            else:
                created += 1
        except Exception as exc:
            session.rollback()
            logger.warning("Project import failed (%s)", type(exc).__name__)
            errors.append(f"Row {idx}: project could not be saved")
    if not dry_run:
        _publish_project_mutation(space_ctx.space_id)
    return {"created": created, "updated": updated, "errors": errors, "total_rows": len(rows), "dry_run": dry_run}


@router.get("/export")
def export_projects(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    rows = (
        _project_query(session, space_ctx)
        .join(Program, Program.program_id == Project.program_id)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .with_entities(Project, Program)
        .all()
    )
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_PROJECT_EXPORT_FIELDNAMES)
    writer.writeheader()
    for project, program in rows:
        writer.writerow(
            {
                "program_id": project.program_id,
                "program_name": program.program_name,
                "project_name": project.project_name,
                "function": project.function or "",
                "area": project.area or "",
                "status": project.status.value if hasattr(project.status, "value") else project.status,
                "description": read_text_value(project.description) or "",
                "success_criteria": read_text_value(project.success_criteria) or "",
                "sponsor": project.sponsor or "",
                "sponsor_user_soeid": project.sponsor_user_soeid or "",
                "owner": project.owner or "",
                "owner_user_soeid": project.owner_user_soeid or "",
                "strategic_objective": read_text_value(project.strategic_objective) or "",
                "priority": project.priority,
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="projects.csv"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)
