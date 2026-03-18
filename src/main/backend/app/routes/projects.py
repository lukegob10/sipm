from datetime import datetime, timezone
from typing import List, Optional

import csv
from io import StringIO
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_space_role,
)
from ..utils.enums import ProjectStatus
from ..models import Project, User
from ..schemas import ProjectCreate, ProjectRead, ProjectUpdate
from ..utils import normalize_status, normalize_str, parse_priority, read_csv, read_text_value
from ..services.realtime import schedule_broadcast
from ..services.audit_log import safe_log_changes
from ..services.spaces import SpaceContext
from ..services.smart_cache import cached_call, invalidate_space, make_scope_token

router = APIRouter()
_PROJECTS_LIST_TTL_SECONDS = 20
_PROJECTS_DETAIL_TTL_SECONDS = 30
_WORK_ALLOCATION_PROJECT_NAME_PREFIX = "Work Allocation Board ["


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _project_payload(project: Project) -> dict:
    return ProjectRead.model_validate(project).model_dump(mode="json")


def _project_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
    )


def _active_project_name_conflict_query(session: Session, *, project_name: str, space_id: str):
    return (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_id)
        .filter(Project.project_name == project_name)
    )


def _exclude_work_allocation_board_projects(query):
    return query.filter(~Project.project_name.like(f"{_WORK_ALLOCATION_PROJECT_NAME_PREFIX}%"))


def _get_project_or_404(session: Session, project_id: str, space_ctx: SpaceContext) -> Project:
    project = (
        session.query(Project)
        .filter(Project.project_id == project_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _is_project_name_conflict_integrity_error(exc: IntegrityError) -> bool:
    parts = [
        str(exc),
        str(getattr(exc, "orig", "")),
        str(getattr(exc, "statement", "")),
    ]
    text = " ".join(parts).lower()
    if "uix_project_space_name" in text or "uix_project_name" in text:
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
    if not has_unique_marker:
        return False
    return ("project_name" in text) or ("tb_ta_pm_projects" in text)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _deleted_project_name(project_name: str, project_id: str, deleted_at: datetime) -> str:
    base = (project_name or "Project").strip() or "Project"
    stamp = _as_utc(deleted_at).strftime("%Y%m%dT%H%M%SZ")
    token = (project_id or "")[:8] or "deleted"
    suffix = f" [deleted {stamp} {token}]"
    max_base_len = max(1, 255 - len(suffix))
    return f"{base[:max_base_len]}{suffix}"


@router.get("", response_model=List[ProjectRead])
@router.get("/", response_model=List[ProjectRead])
def list_projects(
    status_filter: Optional[ProjectStatus] = None,
    sponsor: Optional[str] = None,
    sponsor_user_soeid: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    status_val = status_filter.value if hasattr(status_filter, "value") else status_filter
    sponsor_norm = sponsor.strip().lower() if sponsor else None
    params = {
        "status": status_val,
        "sponsor": sponsor_norm,
        "sponsor_user_soeid": sponsor_user_soeid,
    }
    scope_token = make_scope_token("projects", space_ctx.space_id)

    def _load():
        query = _exclude_work_allocation_board_projects(_project_query(session, space_ctx))
        if status_filter:
            query = query.filter(Project.status == status_filter)
        if sponsor_norm:
            query = query.filter(func.lower(Project.sponsor) == sponsor_norm)
        if sponsor_user_soeid:
            query = query.filter(Project.sponsor_user_soeid == sponsor_user_soeid)
        return [_project_payload(project) for project in query.all()]

    return cached_call(
        endpoint="projects:list",
        params=params,
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PROJECTS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    # Active name conflict in this space should be rejected up-front.
    existing = _active_project_name_conflict_query(
        session,
        project_name=payload.project_name,
        space_id=space_ctx.space_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project name already exists"
        )

    # Backfill legacy deletes (rows soft-deleted before the rename-on-delete behavior)
    # so users can reuse the original project name.
    now = datetime.now(timezone.utc)
    deleted_conflicts = (
        session.query(Project)
        .filter(Project.deleted_at.is_not(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.project_name == payload.project_name)
        .all()
    )
    for deleted in deleted_conflicts:
        deleted.project_name = _deleted_project_name(deleted.project_name, deleted.project_id, deleted.deleted_at or now)
        deleted.updated_at = now
        session.add(deleted)

    sponsor = normalize_str(payload.sponsor) or current_user.display_name or current_user.soeid or "Sponsor"
    sponsor_user_soeid = normalize_str(payload.sponsor_user_soeid) or None
    if sponsor_user_soeid is None and current_user.soeid:
        # Only auto-fill the SOEID when the sponsor resolves to the current user.
        if sponsor == current_user.display_name or sponsor == current_user.soeid:
            sponsor_user_soeid = current_user.soeid

    project = Project(
        space_id=space_ctx.space_id,
        project_name=payload.project_name,
        status=payload.status,
        description=payload.description,
        success_criteria=payload.success_criteria,
        sponsor=sponsor,
        sponsor_user_soeid=sponsor_user_soeid,
        strategic_objective=payload.strategic_objective,
        priority=payload.priority if payload.priority is not None else 3,
    )
    try:
        if deleted_conflicts:
            session.flush()
        session.add(project)
        session.flush()
        safe_log_changes(
            session,
            entity_type="project",
            entity_id=project.project_id,
            user_id=current_user.user_id,
            action="create",
            space_id=space_ctx.space_id,
            changes={
                "project_name": (None, project.project_name),
                "status": (None, project.status),
                "description": (None, project.description),
                "success_criteria": (None, project.success_criteria),
                "sponsor": (None, project.sponsor),
                "sponsor_user_soeid": (None, project.sponsor_user_soeid),
                "strategic_objective": (None, project.strategic_objective),
                "priority": (None, project.priority),
            },
        )
        session.commit()
        session.refresh(project)
    except IntegrityError as exc:
        session.rollback()
        if _is_project_name_conflict_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project name already exists",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project create failed due to a data conflict.",
        ) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create project.",
        ) from exc
    invalidate_space(space_ctx.space_id, ["projects"])
    schedule_broadcast("projects", space_id=space_ctx.space_id)
    return _project_payload(project)


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
    request_id = str(uuid4())

    for idx, row in enumerate(rows, start=2):  # header is row 1
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
                before = {
                    "status": existing.status,
                    "description": existing.description,
                    "success_criteria": existing.success_criteria,
                    "sponsor": existing.sponsor,
                    "sponsor_user_soeid": existing.sponsor_user_soeid,
                    "strategic_objective": existing.strategic_objective,
                    "priority": existing.priority,
                }
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
                    changes={
                        "status": (before["status"], existing.status),
                        "description": (before["description"], existing.description),
                        "success_criteria": (before["success_criteria"], existing.success_criteria),
                        "sponsor": (before["sponsor"], existing.sponsor),
                        "sponsor_user_soeid": (
                            before["sponsor_user_soeid"],
                            existing.sponsor_user_soeid,
                        ),
                        "strategic_objective": (
                            before["strategic_objective"],
                            existing.strategic_objective,
                        ),
                        "priority": (before["priority"], existing.priority),
                    },
                    request_id=request_id,
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
                    changes={
                        "project_name": (None, project.project_name),
                        "status": (None, project.status),
                        "description": (None, project.description),
                        "success_criteria": (None, project.success_criteria),
                        "sponsor": (None, project.sponsor),
                        "sponsor_user_soeid": (None, project.sponsor_user_soeid),
                        "strategic_objective": (None, project.strategic_objective),
                        "priority": (None, project.priority),
                    },
                    request_id=request_id,
                )
                created += 1
            session.commit()
        except Exception as exc:
            session.rollback()
            errors.append(f"Row {idx}: {exc}")
    invalidate_space(space_ctx.space_id, ["projects"])
    schedule_broadcast("projects", space_id=space_ctx.space_id)
    return {"created": created, "updated": updated, "errors": errors, "total_rows": len(rows)}


@router.get("/export")
def export_projects(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
):
    projects = _exclude_work_allocation_board_projects(_project_query(session, space_ctx)).all()
    buffer = StringIO()
    fieldnames = [
        "project_name",
        "status",
        "description",
        "success_criteria",
        "sponsor",
        "sponsor_user_soeid",
        "strategic_objective",
        "priority",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for p in projects:
        writer.writerow(
            {
                "project_name": p.project_name,
                "status": p.status.value if hasattr(p.status, "value") else p.status,
                "description": read_text_value(p.description) or "",
                "success_criteria": read_text_value(p.success_criteria) or "",
                "sponsor": p.sponsor or "",
                "sponsor_user_soeid": p.sponsor_user_soeid or "",
                "strategic_objective": p.strategic_objective or "",
                "priority": p.priority,
            }
        )
    buffer.seek(0)
    headers = {"Content-Disposition": 'attachment; filename="projects.csv"'}
    return StreamingResponse(buffer, media_type="text/csv", headers=headers)


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    scope_token = make_scope_token("projects", space_ctx.space_id)

    def _load():
        return _project_payload(_get_project_or_404(session, project_id, space_ctx))

    return cached_call(
        endpoint="projects:detail",
        params={"project_id": project_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PROJECTS_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    project = _get_project_or_404(session, project_id, space_ctx)

    update_data = payload.model_dump(exclude_unset=True)
    before = {field: getattr(project, field) for field in update_data.keys()}
    for field, value in update_data.items():
        setattr(project, field, value)
    project.updated_at = datetime.now(timezone.utc)

    if "project_name" in update_data and update_data["project_name"]:
        conflict = (
            _project_query(session, space_ctx)
            .filter(Project.project_name == update_data["project_name"])
            .filter(Project.project_id != project.project_id)
            .first()
        )
        if conflict:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Project name already exists"
            )

    try:
        session.add(project)
        if update_data:
            safe_log_changes(
                session,
                entity_type="project",
                entity_id=project.project_id,
                user_id=current_user.user_id,
                action="update",
                space_id=space_ctx.space_id,
                changes={field: (before.get(field), getattr(project, field)) for field in update_data.keys()},
            )
        session.commit()
        session.refresh(project)
    except IntegrityError as exc:
        session.rollback()
        if _is_project_name_conflict_integrity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project name already exists",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Project update failed due to a data conflict.",
        ) from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update project.",
        ) from exc
    invalidate_space(space_ctx.space_id, ["projects"])
    schedule_broadcast("projects", space_id=space_ctx.space_id)
    return _project_payload(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    project = _get_project_or_404(session, project_id, space_ctx)
    now = datetime.now(timezone.utc)
    previous_name = project.project_name
    project.deleted_at = now
    project.updated_at = now
    project.project_name = _deleted_project_name(project.project_name, project.project_id, now)
    session.add(project)
    safe_log_changes(
        session,
        entity_type="project",
        entity_id=project.project_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={
            "deleted_at": (None, now),
            "project_name": (previous_name, project.project_name),
        },
    )
    session.commit()
    invalidate_space(space_ctx.space_id, ["projects"])
    schedule_broadcast("projects", space_id=space_ctx.space_id)
    return None


