from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...models import Program, Project
from ...schemas import ProjectRead
from ...services.mutations import publish_space_mutation
from ...services.realtime import schedule_broadcast
from ...services.smart_cache import invalidate_space
from ...services.spaces import SpaceContext
from ...utils import normalize_str

_PROJECTS_LIST_TTL_SECONDS = 20
_PROJECTS_DETAIL_TTL_SECONDS = 30
_PROJECT_CREATE_AUDIT_FIELDS = (
    "program_id",
    "project_name",
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


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _project_payload(project: Project, *, program_name: str | None = None) -> dict:
    data = ProjectRead.model_validate(project).model_dump(mode="json")
    data["program_name"] = program_name
    return data


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


def _ensure_program_exists(session: Session, program_id: str, space_ctx: SpaceContext) -> Program:
    program = (
        session.query(Program)
        .filter(Program.program_id == program_id)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
        .first()
    )
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


def _default_program(session: Session, space_ctx: SpaceContext) -> Program:
    from ..programs import ensure_default_program

    return ensure_default_program(session, space_ctx)


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


def _resolve_project_sponsor(
    sponsor_value: object | None,
    sponsor_user_soeid_value: object | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    sponsor = normalize_str(sponsor_value) or display_name or current_soeid or "Sponsor"
    sponsor_user_soeid = normalize_str(sponsor_user_soeid_value) or None
    if sponsor_user_soeid is None and current_soeid and sponsor in {display_name, current_soeid}:
        sponsor_user_soeid = current_soeid
    return sponsor, sponsor_user_soeid


def _resolve_project_owner(
    owner_value: object | None,
    owner_user_soeid_value: object | None,
    current_user: object,
) -> tuple[str, str | None]:
    display_name = normalize_str(getattr(current_user, "display_name", None))
    current_soeid = normalize_str(getattr(current_user, "soeid", None))
    owner = normalize_str(owner_value) or display_name or current_soeid or ""
    owner_user_soeid = normalize_str(owner_user_soeid_value) or None
    if owner_user_soeid is None and current_soeid and owner in {display_name, current_soeid}:
        owner_user_soeid = current_soeid
    return owner, owner_user_soeid


def _project_create_changes(project: Project) -> dict[str, tuple[object | None, object | None]]:
    return {field: (None, getattr(project, field)) for field in _PROJECT_CREATE_AUDIT_FIELDS}


def _project_change_set(
    project: Project,
    before: dict[str, object | None],
    fields: Iterable[str],
) -> dict[str, tuple[object | None, object | None]]:
    return {field: (before.get(field), getattr(project, field)) for field in fields}


def _publish_project_mutation(space_id: str) -> None:
    publish_space_mutation(space_id, ["projects"], broadcast_channel="projects")


def _publish_project_deletion(space_id: str) -> None:
    invalidate_space(space_id, ["projects", "solutions", "tasks"])
    schedule_broadcast("projects", space_id=space_id)
    schedule_broadcast("solutions", space_id=space_id)
    schedule_broadcast("tasks", space_id=space_id)


__all__ = [
    "_PROJECTS_DETAIL_TTL_SECONDS",
    "_PROJECTS_LIST_TTL_SECONDS",
    "_active_project_name_conflict_query",
    "_default_program",
    "_deleted_project_name",
    "_ensure_program_exists",
    "_get_project_or_404",
    "_is_project_name_conflict_integrity_error",
    "_project_change_set",
    "_project_create_changes",
    "_project_payload",
    "_project_query",
    "_publish_project_deletion",
    "_publish_project_mutation",
    "_resolve_project_sponsor",
    "_resolve_project_owner",
    "_role_scope",
]
