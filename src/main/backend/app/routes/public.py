from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models import Phase, Program, Project, Solution, Space
from ..phase_catalog import canonical_phase_query
from ..routes.projects.common import _project_payload
from ..routes.solutions.common import _solution_payload
from ..schemas import PhaseRead, ProgramDashboardReportRequest, ProgramRead
from ..services.program_dashboard_report_pdf import build_program_dashboard_report_pdf
from ..services.program_dashboard_report_data import load_program_dashboard_report_data
from ..services.program_dashboard_report_xlsx import build_program_dashboard_report_xlsx

router = APIRouter(prefix="/public")


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public dashboard not found")


def _public_dashboard_space_or_404(space_slug: str, session: Session) -> Space:
    slug = str(space_slug or "").strip().lower()
    if not slug:
        raise _not_found()
    space = (
        session.query(Space)
        .filter(Space.slug == slug)
        .filter(Space.deleted_at.is_(None))
        .filter(Space.is_active)
        .filter(Space.public_program_dashboard_enabled)
        .first()
    )
    if not space:
        raise _not_found()
    return space


@router.get("/program-dashboard/{space_slug}")
def get_public_program_dashboard(space_slug: str, session: Session = Depends(get_db)) -> dict:
    space = _public_dashboard_space_or_404(space_slug, session)
    programs = (
        session.query(Program)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space.space_id)
        .order_by(Program.program_name.asc())
        .all()
    )
    projects = (
        session.query(Project)
        .join(Program, Program.program_id == Project.program_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space.space_id)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space.space_id)
        .order_by(Project.project_name.asc())
        .all()
    )
    solutions = (
        session.query(Solution)
        .join(Project, Project.project_id == Solution.project_id)
        .filter(Solution.deleted_at.is_(None))
        .filter(Solution.space_id == space.space_id)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space.space_id)
        .order_by(Solution.priority.asc(), Solution.created_at.asc())
        .all()
    )
    phases = canonical_phase_query(session).order_by(Phase.sequence.asc()).all()

    return {
        "space": {
            "space_id": space.space_id,
            "space_name": space.name,
            "slug": space.slug,
        },
        "phases": [PhaseRead.model_validate(row).model_dump(mode="json") for row in phases],
        "programs": [ProgramRead.model_validate(row).model_dump(mode="json") for row in programs],
        "projects": [_project_payload(row) for row in projects],
        "solutions": [_solution_payload(row) for row in solutions],
    }


@router.post("/program-dashboard/{space_slug}/report.pdf")
def download_public_program_dashboard_report_pdf(
    space_slug: str,
    payload: ProgramDashboardReportRequest,
    session: Session = Depends(get_db),
) -> StreamingResponse:
    space = _public_dashboard_space_or_404(space_slug, session)
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

    program_query = (
        session.query(Program)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space.space_id)
    )
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
            .filter(Project.space_id == space.space_id)
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
            .filter(Solution.space_id == space.space_id)
            .filter(Solution.project_id.in_(valid_project_ids))
            .order_by(Solution.solution_name.asc())
            .all()
        )

    phase_rows = canonical_phase_query(session).order_by(Phase.sequence.asc()).all()
    program_label = (
        program_rows[0].program_name
        if len(program_rows) == 1
        else f"{len(program_rows)} selected"
    )
    pdf_bytes = build_program_dashboard_report_pdf(
        space_name=space.name,
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


@router.post("/program-dashboard/{space_slug}/report.xlsx")
def download_public_program_dashboard_report_xlsx(
    space_slug: str,
    payload: ProgramDashboardReportRequest,
    session: Session = Depends(get_db),
) -> StreamingResponse:
    space = _public_dashboard_space_or_404(space_slug, session)
    selected_program_ids = [
        str(program_id or "").strip()
        for program_id in payload.selected_program_ids
        if str(program_id or "").strip()
    ]
    report_data = load_program_dashboard_report_data(
        session,
        space_id=space.space_id,
        selected_program_ids=selected_program_ids,
    )
    xlsx_bytes = build_program_dashboard_report_xlsx(
        space_name=space.name,
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
