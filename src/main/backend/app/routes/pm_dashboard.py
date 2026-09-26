from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, load_only

from ..deps import current_space as current_space_dep, get_db, require_space_role
from ..models import Project, Solution, Task
from ..services.pm_command_report_pdf import build_pm_command_report_pdf
from ..services.spaces import SpaceContext

router = APIRouter()


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
        .options(
            load_only(
                Project.project_id,
                Project.project_name,
                Project.status,
                Project.sponsor,
                Project.sponsor_user_soeid,
                Project.owner,
                Project.owner_user_soeid,
                Project.priority,
                Project.updated_at,
            )
        )
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
            .options(
                load_only(
                    Solution.solution_id,
                    Solution.project_id,
                    Solution.solution_name,
                    Solution.status,
                    Solution.rag_status,
                    Solution.due_date,
                    Solution.owner,
                    Solution.owner_user_soeid,
                    Solution.assignee,
                    Solution.assignee_user_soeid,
                    Solution.blockers,
                    Solution.risks,
                    Solution.updated_at,
                )
            )
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
            .options(
                load_only(
                    Task.task_id,
                    Task.project_id,
                    Task.solution_id,
                    Task.task_name,
                    Task.status,
                    Task.due_date,
                    Task.assignee,
                    Task.assignee_user_soeid,
                    Task.blocked,
                    Task.blocker_note,
                    Task.updated_at,
                )
            )
            .filter(Task.deleted_at.is_(None))
            .filter(Task.space_id == space_ctx.space_id)
            .filter(Task.solution_id.in_(solution_ids))
            .order_by(Task.priority.asc(), Task.task_name.asc())
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
                "owner": row.owner,
                "owner_user_soeid": row.owner_user_soeid,
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
        users=[],
        allocations=[],
    )
    filename = f"pm-command-center-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
