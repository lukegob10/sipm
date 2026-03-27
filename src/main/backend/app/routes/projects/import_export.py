from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_space_role
from ...models import Project, User
from ...services.audit_log import safe_log_changes
from ...services.spaces import SpaceContext
from ...utils import normalize_status, normalize_str, parse_priority, read_csv, read_text_value
from ...utils.enums import ProjectStatus
from .common import (
    _exclude_work_allocation_board_projects,
    _project_change_set,
    _project_create_changes,
    _project_query,
    _publish_project_mutation,
)

router = APIRouter()
_PROJECT_IMPORT_UPDATE_FIELDS = (
    "status",
    "description",
    "success_criteria",
    "sponsor",
    "sponsor_user_soeid",
    "strategic_objective",
    "priority",
)
_PROJECT_EXPORT_FIELDNAMES = [
    "project_name",
    "status",
    "description",
    "success_criteria",
    "sponsor",
    "sponsor_user_soeid",
    "strategic_objective",
    "priority",
]


@router.post("/import")
def import_projects(
    csv_bytes: bytes = Body(..., media_type="text/csv"),
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    rows, errors = read_csv(csv_bytes)
    if errors:
        return {"created": 0, "updated": 0, "errors": errors, "total_rows": 0}
    created = updated = 0
    seen = set()
    for idx, row in enumerate(rows, start=2):
        name = normalize_str(row.get("project_name"))
        sponsor = normalize_str(row.get("sponsor"))
        if not name:
            errors.append(f"Row {idx}: project_name is required")
            continue
        if not sponsor:
            errors.append(f"Row {idx}: sponsor is required")
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
        existing = _project_query(session, space_ctx).filter(Project.project_name == name).first()
        try:
            if existing:
                before = {field: getattr(existing, field) for field in _PROJECT_IMPORT_UPDATE_FIELDS}
                existing.status = status_enum
                existing.description = description
                existing.success_criteria = success_criteria
                existing.sponsor = sponsor
                existing.sponsor_user_soeid = sponsor_user_soeid
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
                updated += 1
            else:
                project = Project(
                    space_id=space_ctx.space_id,
                    project_name=name,
                    status=status_enum,
                    description=description,
                    success_criteria=success_criteria,
                    sponsor=sponsor,
                    sponsor_user_soeid=sponsor_user_soeid,
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
                created += 1
            session.commit()
        except Exception as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")
    _publish_project_mutation(space_ctx.space_id)
    return {"created": created, "updated": updated, "errors": errors, "total_rows": len(rows)}


@router.get("/export")
def export_projects(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    projects = _exclude_work_allocation_board_projects(_project_query(session, space_ctx)).all()
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_PROJECT_EXPORT_FIELDNAMES)
    writer.writeheader()
    for project in projects:
        writer.writerow(
            {
                "project_name": project.project_name,
                "status": project.status.value if hasattr(project.status, "value") else project.status,
                "description": read_text_value(project.description) or "",
                "success_criteria": read_text_value(project.success_criteria) or "",
                "sponsor": project.sponsor or "",
                "sponsor_user_soeid": project.sponsor_user_soeid or "",
                "strategic_objective": project.strategic_objective or "",
                "priority": project.priority,
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="projects.csv"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)
