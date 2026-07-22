from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...deps import current_space as current_space_dep
from ...deps import current_user as current_user_dep
from ...deps import get_db
from ...models import Program, Project, User
from ...schemas import ProjectRead
from ...services.smart_cache import cached_call, make_scope_token
from ...services.spaces import SpaceContext
from ...utils.enums import ProjectStatus
from .common import (
    _PROJECTS_DETAIL_TTL_SECONDS,
    _PROJECTS_LIST_TTL_SECONDS,
    _get_project_or_404,
    _project_payload,
    _project_query,
    _role_scope,
)

router = APIRouter()


def list_projects(
    status_filter: Optional[ProjectStatus] = None,
    program_id: Optional[str] = None,
    sponsor: Optional[str] = None,
    sponsor_user_soeid: Optional[str] = None,
    owner: Optional[str] = None,
    owner_user_soeid: Optional[str] = None,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    status_val = status_filter.value if hasattr(status_filter, "value") else status_filter
    sponsor_norm = sponsor.strip().lower() if sponsor else None
    owner_norm = owner.strip().lower() if owner else None
    params = {
        "status": status_val,
        "program_id": program_id,
        "sponsor": sponsor_norm,
        "sponsor_user_soeid": sponsor_user_soeid,
        "owner": owner_norm,
        "owner_user_soeid": owner_user_soeid,
    }
    scope_token = make_scope_token("projects", space_ctx.space_id)

    def _load():
        query = (
            _project_query(session, space_ctx)
            .join(Program, Program.program_id == Project.program_id)
            .filter(Program.deleted_at.is_(None))
        )
        if status_filter:
            query = query.filter(Project.status == status_filter)
        if program_id:
            query = query.filter(Project.program_id == program_id)
        if sponsor_norm:
            query = query.filter(func.lower(Project.sponsor) == sponsor_norm)
        if sponsor_user_soeid:
            query = query.filter(Project.sponsor_user_soeid == sponsor_user_soeid)
        if owner_norm:
            query = query.filter(func.lower(Project.owner) == owner_norm)
        if owner_user_soeid:
            query = query.filter(Project.owner_user_soeid == owner_user_soeid)
        return [
            _project_payload(project, program_name=program.program_name)
            for project, program in query.with_entities(Project, Program).all()
        ]

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


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
):
    scope_token = make_scope_token("projects", space_ctx.space_id)

    def _load():
        project = _get_project_or_404(session, project_id, space_ctx)
        program = (
            session.query(Program)
            .filter(Program.program_id == project.program_id)
            .filter(Program.space_id == space_ctx.space_id)
            .first()
        )
        return _project_payload(project, program_name=program.program_name if program else None)

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
