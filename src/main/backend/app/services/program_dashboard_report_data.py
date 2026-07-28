from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Phase, Program, Project, Solution


def load_program_dashboard_report_data(
    session: Session,
    *,
    space_id: str,
    selected_program_ids: list[str],
) -> dict[str, object]:
    program_query = (
        session.query(Program)
        .filter(Program.deleted_at.is_(None))
        .filter(Program.space_id == space_id)
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
            .filter(Project.space_id == space_id)
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
            .filter(Solution.space_id == space_id)
            .filter(Solution.project_id.in_(valid_project_ids))
            .order_by(Solution.solution_name.asc())
            .all()
        )
    phase_rows = session.query(Phase).order_by(Phase.sequence.asc()).all()

    return {
        "selected_program_label": (
            program_rows[0].program_name if len(program_rows) == 1 else f"{len(program_rows)} selected"
        ),
        "programs": [
            {"program_id": row.program_id, "program_name": row.program_name}
            for row in program_rows
        ],
        "projects": [
            {
                "project_id": row.project_id,
                "program_id": row.program_id,
                "project_name": row.project_name,
                "description": row.description,
                "status": row.status.value if hasattr(row.status, "value") else row.status,
                "sponsor": row.sponsor,
                "sponsor_user_soeid": row.sponsor_user_soeid,
                "owner": row.owner,
                "owner_user_soeid": row.owner_user_soeid,
            }
            for row in project_rows
        ],
        "solutions": [
            {
                "solution_id": row.solution_id,
                "project_id": row.project_id,
                "solution_name": row.solution_name,
                "description": row.description,
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
        "phases": [
            {"phase_id": row.phase_id, "phase_name": row.phase_name, "sequence": row.sequence}
            for row in phase_rows
        ],
    }


__all__ = ["load_program_dashboard_report_data"]
