from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..deps import current_space as current_space_dep, get_db, require_space_role
from ..models import Project, ResourceAllocation, Solution, Task, User
from ..routes.projects.common import _exclude_work_allocation_board_projects
from ..routes.solutions.common import _exclude_work_allocation_board_solutions
from ..services.pm_command_report_pdf import build_pm_command_report_pdf
from ..services.planning_work_allocation import active_space_user_query
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
        _exclude_work_allocation_board_projects(
            session.query(Project)
            .filter(Project.deleted_at.is_(None))
            .filter(Project.space_id == space_ctx.space_id)
        )
        .order_by(Project.priority.asc(), Project.project_name.asc())
        .all()
    )
    project_ids = [row.project_id for row in project_rows]
    solution_rows = []
    if project_ids:
        solution_rows = (
            _exclude_work_allocation_board_solutions(
                session.query(Solution)
                .filter(Solution.deleted_at.is_(None))
                .filter(Solution.space_id == space_ctx.space_id)
                .filter(Solution.project_id.in_(project_ids)),
                session,
                space_ctx,
            )
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
    task_ids = [row.task_id for row in task_rows]
    user_rows = (
        active_space_user_query(session, space_ctx)
        .order_by(User.display_name.asc())
        .all()
    )
    allocation_rows = []
    if task_ids:
        allocation_rows = (
            session.query(ResourceAllocation)
            .filter(ResourceAllocation.deleted_at.is_(None))
            .filter(ResourceAllocation.space_id == space_ctx.space_id)
            .filter(ResourceAllocation.work_item_type == "task")
            .filter(ResourceAllocation.work_item_id.in_(task_ids))
            .order_by(ResourceAllocation.created_at.asc())
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
        allocations=[
            {
                "allocation_id": row.allocation_id,
                "work_item_type": row.work_item_type,
                "work_item_id": row.work_item_id,
                "assignee_user_soeid": row.assignee_user_soeid,
                "assignee": row.assignee,
                "week_start": row.week_start,
                "month_start": row.month_start,
                "hours": row.hours,
                "fte_months": row.fte_months,
            }
            for row in allocation_rows
        ],
    )
    filename = f"pm-command-center-report-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.pdf"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers=headers)
