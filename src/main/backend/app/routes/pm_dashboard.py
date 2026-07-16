from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..deps import current_space as current_space_dep, get_db, require_space_role
from ..models import Project, Solution, SpaceMembership, Task, User
from ..services.pm_command_report_pdf import build_pm_command_report_pdf
from ..services.spaces import SpaceContext

router = APIRouter()


def active_space_user_query(session: Session, space_ctx: SpaceContext):
    return (
        session.query(User)
        .join(SpaceMembership, SpaceMembership.user_id == User.user_id)
        .filter(SpaceMembership.space_id == space_ctx.space_id)
        .filter(SpaceMembership.deleted_at.is_(None))
        .filter(SpaceMembership.status == "active")
        .filter(User.is_active)
    )


def _enum_value(value: object) -> object:
    return value.value if hasattr(value, "value") else value


@router.get("/pm-dashboard/report.pdf")
def download_pm_command_report_pdf(
    session: Session = Depends(get_db),
    space_ctx: SpaceContext = Depends(current_space_dep),
    _authz: SpaceContext = Depends(require_space_role("member")),
) -> StreamingResponse:
    project_rows = (
        session.query(Project)
        .filter(Project.deleted_at.is_(None))
        .filter(Project.space_id == space_ctx.space_id)
        .order_by(Project.priority.asc(), Project.project_name.asc())
        .all()
    )
    project_ids = [row.project_id for row in project_rows]
    solution_rows = []
    if project_ids:
        solution_rows = (
            session.query(Solution)
            .filter(Solution.deleted_at.is_(None))
            .filter(Solution.space_id == space_ctx.space_id)
            .filter(Solution.project_id.in_(project_ids))
            .order_by(Solution.priority.asc(), Solution.solution_name.asc())
            .all()
        )
    solution_ids = [row.solution_id for row in solution_rows]
    task_rows = []
    if solution_ids:
        task_rows = (
            session.query(Task)
            .filter(Task.deleted_at.is_(None))
            .filter(Task.space_id == space_ctx.space_id)
            .filter(Task.solution_id.in_(solution_ids))
            .order_by(Task.priority.asc(), Task.task_name.asc())
            .all()
        )
    user_rows = (
        active_space_user_query(session, space_ctx)
        .order_by(User.display_name.asc())
        .all()
    )
    pdf_bytes = build_pm_command_report_pdf(
        space_name=space_ctx.space_name,
        projects=[
            {
                "project_id": row.project_id,
                "project_name": row.project_name,
                "status": _enum_value(row.status),
                "sponsor": row.sponsor,
                "sponsor_user_soeid": row.sponsor_user_soeid,
                "priority": row.priority,
                "updated_at": row.updated_at,
            }
            for row in project_rows
        ],
        solutions=[
            {
                "solution_id": row.solution_id,
                "project_id": row.project_id,
                "solution_name": row.solution_name,
                "status": _enum_value(row.status),
                "rag_status": _enum_value(row.rag_status),
                "due_date": row.due_date,
                "owner": row.owner,
                "owner_user_soeid": row.owner_user_soeid,
                "assignee": row.assignee,
                "assignee_user_soeid": row.assignee_user_soeid,
                "blockers": row.blockers,
                "risks": row.risks,
                "updated_at": row.updated_at,
            }
            for row in solution_rows
        ],
        tasks=[
            {
                "task_id": row.task_id,
                "project_id": row.project_id,
                "solution_id": row.solution_id,
                "task_name": row.task_name,
                "status": _enum_value(row.status),
                "due_date": row.due_date,
                "assignee": row.assignee,
                "assignee_user_soeid": row.assignee_user_soeid,
                "blocked": row.blocked,
                "blocker_note": row.blocker_note,
                "updated_at": row.updated_at,
            }
            for row in task_rows
        ],
        users=[
            {
                "soeid": row.soeid,
                "display_name": row.display_name,
                "capacity_fte_month": row.capacity_fte_month,
                "is_active": row.is_active,
            }
            for row in user_rows
        ],
        allocations=[],
    )
    filename = f"pm-command-center-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
