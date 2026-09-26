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
    report_data = load_program_dashboard_report_data(
        session,
        space_id=space.space_id,
        selected_program_ids=payload.selected_program_ids,
    )
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

    pdf_bytes = build_program_dashboard_report_pdf(
        space_name=space.name,
        selected_program_label=str(report_data["selected_program_label"]),
        programs=report_data["programs"],
        projects=report_data["projects"],
        solutions=report_data["solutions"],
        phases=report_data["phases"],
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
    report_data = load_program_dashboard_report_data(
        session,
        space_id=space.space_id,
        selected_program_ids=payload.selected_program_ids,
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
