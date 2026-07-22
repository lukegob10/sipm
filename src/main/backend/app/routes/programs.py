from __future__ import annotations

from io import BytesIO
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..deps import (
    current_space as current_space_dep,
    current_user as current_user_dep,
    get_db,
    require_non_agent_write,
    require_space_role,
)
from ..models import Phase, Program, Project, Solution, User
from ..schemas import ProgramCreate, ProgramDashboardReportRequest, ProgramRead, ProgramUpdate
from ..services.audit_log import safe_log_changes
from ..services.mutations import publish_space_mutation
from ..services.program_dashboard_report_pdf import build_program_dashboard_report_pdf
from ..services.program_dashboard_report_data import load_program_dashboard_report_data
from ..services.program_dashboard_report_xlsx import build_program_dashboard_report_xlsx
from ..services.smart_cache import cached_call, make_scope_token
from ..services.spaces import SpaceContext
from ..utils import normalize_str

router = APIRouter(prefix="/programs")
DEFAULT_PROGRAM_NAME = "Default Program"
_PROGRAMS_LIST_TTL_SECONDS = 20
_PROGRAMS_DETAIL_TTL_SECONDS = 30


def _role_scope(space_ctx: SpaceContext) -> str:
    if space_ctx.is_global_admin:
        return "global_admin"
    return space_ctx.space_role or "member"


def _required_program_name(value: object) -> str:
    program_name = normalize_str(value)
    if not program_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="program_name is required",
        )
    return program_name


def _program_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(Program)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_ctx.space_id)
    )


def _program_payload(program: Program) -> dict:
    return ProgramRead.model_validate(program).model_dump(mode="json")


def _get_program_or_404(session: Session, program_id: str, space_ctx: SpaceContext) -> Program:
    program = (
        _program_query(session, space_ctx)
        .filter(Program.program_id == program_id)
        .first()
    )
    if not program:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Program not found")
    return program


def _ensure_program_exists(session: Session, program_id: str, space_ctx: SpaceContext) -> Program:
    return _get_program_or_404(session, program_id, space_ctx)


def ensure_default_program(session: Session, space_ctx: SpaceContext) -> Program:
    program = (
        session.query(Program)
        .filter(Program.space_id == space_ctx.space_id)
        .filter(Program.program_name == DEFAULT_PROGRAM_NAME)
        .first()
    )
    now = datetime.now(timezone.utc)
    if program and program.deleted_at is None:
        return program
    if program:
        program.deleted_at = None
        program.updated_at = now
        session.add(program)
        session.flush()
        return program
    program = Program(
        space_id=space_ctx.space_id,
        program_name=DEFAULT_PROGRAM_NAME,
        description="Default umbrella program for existing projects.",
        created_at=now,
        updated_at=now,
    )
    session.add(program)
    session.flush()
    return program


def _publish_program_mutation(space_id: str, *, include_projects: bool = False) -> None:
    keys = ["programs"]
    if include_projects:
        keys.append("projects")
    publish_space_mutation(space_id, keys, broadcast_channel="programs")
    if include_projects:
        publish_space_mutation(space_id, ["projects"], broadcast_channel="projects")


def _is_program_name_conflict_integrity_error(exc: IntegrityError) -> bool:
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
    return has_unique_marker and ("program_name" in text or "tb_ta_pm_programs" in text)


@router.get("", response_model=List[ProgramRead])
@router.get("/", response_model=List[ProgramRead])
def list_programs(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
) -> list[dict]:
    scope_token = make_scope_token("programs", space_ctx.space_id)

    def _load():
        rows = _program_query(session, space_ctx).order_by(Program.program_name.asc()).all()
        return [_program_payload(row) for row in rows]

    return cached_call(
        endpoint="programs:list",
        params={},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PROGRAMS_LIST_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("/dashboard/report.pdf")
def download_program_dashboard_report_pdf(
    payload: ProgramDashboardReportRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> StreamingResponse:
    selected_program_ids = [
        str(program_id or "").strip()
        for program_id in payload.selected_program_ids
        if str(program_id or "").strip()
    ]
    collapsed_program_ids = {
        str(program_id or "").strip()
        for program_id in payload.collapsed_program_ids
        if str(program_id or "").strip()
    }
    collapsed_project_ids = {
        str(project_id or "").strip()
        for project_id in payload.collapsed_project_ids
        if str(project_id or "").strip()
    }

    program_query = _program_query(session, space_ctx)
    if selected_program_ids:
        program_query = program_query.filter(Program.program_id.in_(selected_program_ids))
    else:
        program_query = program_query.filter(False)
    program_rows = program_query.order_by(Program.program_name.asc()).all()
    valid_program_ids = {row.program_id for row in program_rows}

    project_rows = []
    if valid_program_ids:
        project_rows = (
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.space_id == space_ctx.space_id)
            .filter(Project.program_id.in_(valid_program_ids))
            .order_by(Project.project_name.asc())
            .all()
        )
    valid_project_ids = {row.project_id for row in project_rows}

    solution_rows = []
    if valid_project_ids:
        solution_rows = (
            session.query(Solution)
            .filter(Solution.deleted_at.is_(None))
            .filter(Solution.space_id == space_ctx.space_id)
            .filter(Solution.project_id.in_(valid_project_ids))
            .order_by(Solution.solution_name.asc())
            .all()
        )

    phase_rows = session.query(Phase).order_by(Phase.sequence.asc()).all()
    program_label = (
        program_rows[0].program_name
        if len(program_rows) == 1
        else f"{len(program_rows)} selected"
    )
    pdf_bytes = build_program_dashboard_report_pdf(
        space_name=space_ctx.space_name,
        selected_program_label=program_label,
        programs=[
            {
                "program_id": row.program_id,
                "program_name": row.program_name,
            }
            for row in program_rows
        ],
        projects=[
            {
                "project_id": row.project_id,
                "program_id": row.program_id,
                "project_name": row.project_name,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
                "sponsor": row.sponsor,
                "sponsor_user_soeid": row.sponsor_user_soeid,
                "owner": row.owner,
                "owner_user_soeid": row.owner_user_soeid,
            }
            for row in project_rows
        ],
        solutions=[
            {
                "solution_id": row.solution_id,
                "project_id": row.project_id,
                "solution_name": row.solution_name,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
                "planned_start_date": row.planned_start_date,
                "due_date": row.due_date,
                "current_phase": row.current_phase,
                "escalation": row.escalation,
                "owner": row.owner,
                "owner_user_soeid": row.owner_user_soeid,
                "assignee": row.assignee,
                "key_stakeholder": row.key_stakeholder,
            }
            for row in solution_rows
        ],
        phases=[
            {
                "phase_id": row.phase_id,
                "phase_name": row.phase_name,
                "sequence": row.sequence,
            }
            for row in phase_rows
        ],
        collapsed_program_ids=collapsed_program_ids,
        collapsed_project_ids=collapsed_project_ids,
    )
    filename = f"program-dashboard-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)


@router.post("/dashboard/report.xlsx")
def download_program_dashboard_report_xlsx(
    payload: ProgramDashboardReportRequest,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> StreamingResponse:
    selected_program_ids = [
        str(program_id or "").strip()
        for program_id in payload.selected_program_ids
        if str(program_id or "").strip()
    ]
    report_data = load_program_dashboard_report_data(
        session,
        space_id=space_ctx.space_id,
        selected_program_ids=selected_program_ids,
    )
    xlsx_bytes = build_program_dashboard_report_xlsx(
        space_name=space_ctx.space_name,
        selected_program_label=str(report_data["selected_program_label"]),
        programs=report_data["programs"],
        projects=report_data["projects"],
        solutions=report_data["solutions"],
        phases=report_data["phases"],
        collapsed_program_ids={
            str(program_id or "").strip()
            for program_id in payload.collapsed_program_ids
            if str(program_id or "").strip()
        },
        collapsed_project_ids={
            str(project_id or "").strip()
            for project_id in payload.collapsed_project_ids
            if str(project_id or "").strip()
        },
    )
    filename = f"program-dashboard-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.xlsx"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/{program_id}", response_model=ProgramRead)
def get_program(
    program_id: str,
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    current_user: User = Depends(current_user_dep),
) -> dict:
    scope_token = make_scope_token("programs", space_ctx.space_id)

    def _load():
        return _program_payload(_get_program_or_404(session, program_id, space_ctx))

    return cached_call(
        endpoint="programs:detail",
        params={"program_id": program_id},
        space_id=space_ctx.space_id,
        user_id=current_user.user_id,
        role_scope=_role_scope(space_ctx),
        ttl_seconds=_PROGRAMS_DETAIL_TTL_SECONDS,
        scope_tokens=[scope_token],
        loader=_load,
    )


@router.post("", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ProgramRead, status_code=status.HTTP_201_CREATED)
def create_program(
    payload: ProgramCreate,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> dict:
    program_name = _required_program_name(payload.program_name)
    if _program_query(session, space_ctx).filter(Program.program_name == program_name).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Program name already exists")
    now = datetime.now(timezone.utc)
    program = Program(
        space_id=space_ctx.space_id,
        program_name=program_name,
        description=payload.description,
        created_at=now,
        updated_at=now,
    )
    try:
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
        session.commit()
        session.refresh(program)
    except IntegrityError as exc:
        session.rollback()
        if _is_program_name_conflict_integrity_error(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Program name already exists") from exc
        raise
    _publish_program_mutation(space_ctx.space_id)
    return _program_payload(program)


@router.patch("/{program_id}", response_model=ProgramRead)
def update_program(
    program_id: str,
    payload: ProgramUpdate,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> dict:
    program = _get_program_or_404(session, program_id, space_ctx)
    update_data = payload.model_dump(exclude_unset=True)
    if "program_name" in update_data:
        update_data["program_name"] = _required_program_name(update_data["program_name"])
        conflict = (
            _program_query(session, space_ctx)
            .filter(Program.program_name == update_data["program_name"])
            .filter(Program.program_id != program.program_id)
            .first()
        )
        if conflict:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Program name already exists")
    before = {field: getattr(program, field) for field in update_data}
    for field, value in update_data.items():
        setattr(program, field, value)
    program.updated_at = datetime.now(timezone.utc)
    try:
        session.add(program)
        if update_data:
            safe_log_changes(
                session,
                entity_type="program",
                entity_id=program.program_id,
                user_id=current_user.user_id,
                action="update",
                space_id=space_ctx.space_id,
                changes={field: (before.get(field), getattr(program, field)) for field in update_data},
            )
        session.commit()
        session.refresh(program)
    except IntegrityError as exc:
        session.rollback()
        if _is_program_name_conflict_integrity_error(exc):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Program name already exists") from exc
        raise
    _publish_program_mutation(space_ctx.space_id, include_projects="program_name" in update_data)
    return _program_payload(program)


@router.delete("/{program_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_program(
    program_id: str,
    session: Session = Depends(get_db),
    current_user: User = Depends(current_user_dep),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
    _write_gate: User = Depends(require_non_agent_write),
) -> None:
    program = _get_program_or_404(session, program_id, space_ctx)
    active_project_count = (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .filter(Project.program_id == program.program_id)
        .count()
    )
    if active_project_count:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Program cannot be deleted while it has active projects",
        )
    now = datetime.now(timezone.utc)
    program.deleted_at = now
    program.updated_at = now
    session.add(program)
    safe_log_changes(
        session,
        entity_type="program",
        entity_id=program.program_id,
        user_id=current_user.user_id,
        action="delete",
        space_id=space_ctx.space_id,
        changes={"deleted_at": (None, now)},
    )
    session.commit()
    _publish_program_mutation(space_ctx.space_id)
    return None


__all__ = [
    "DEFAULT_PROGRAM_NAME",
    "ensure_default_program",
    "_ensure_program_exists",
    "_get_program_or_404",
    "_program_query",
    "router",
]
