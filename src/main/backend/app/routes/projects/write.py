from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db, require_space_role
from ...models import Project, User
from ...schemas import ProjectCreate, ProjectRead, ProjectUpdate
from ...services.audit_log import safe_log_changes
from ...services.spaces import SpaceContext
from .common import (
    _active_project_name_conflict_query,
    _deleted_project_name,
    _get_project_or_404,
    _is_project_name_conflict_integrity_error,
    _project_change_set,
    _project_create_changes,
    _project_payload,
    _project_query,
    _publish_project_deletion,
    _publish_project_mutation,
    _resolve_project_sponsor,
)

router = APIRouter()


def create_project(
    payload: ProjectCreate,
    session: Session = Depends(get_db),
    tasks: BackgroundTasks = None,
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("space_admin")),
):
    existing = _active_project_name_conflict_query(
        session,
        project_name=payload.project_name,
        space_id=space_ctx.space_id,
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Project name already exists"
        )

    now = datetime.now(timezone.utc)
    deleted_conflicts = (
        session.query(Project)
        .filter(Project.deleted_at.is_not(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.project_name == payload.project_name)
        .all()
    )
    for deleted in deleted_conflicts:
        deleted.project_name = _deleted_project_name(
            deleted.project_name,
            deleted.project_id,
            deleted.deleted_at or now,
        )
        deleted.updated_at = now
        session.add(deleted)

    sponsor, sponsor_user_soeid = _resolve_project_sponsor(
        payload.sponsor,
        payload.sponsor_user_soeid,
        current_user,
    )

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
            changes=_project_create_changes(project),
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
    _publish_project_mutation(space_ctx.space_id)
    return _project_payload(project)


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
                changes=_project_change_set(project, before, update_data.keys()),
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
    _publish_project_mutation(space_ctx.space_id)
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
    _publish_project_deletion(space_ctx.space_id)
    return None
