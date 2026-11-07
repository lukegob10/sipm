from datetime import date, datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Phase, Program, Project, Solution
from backend.app.services.program_dashboard_report_data import load_program_dashboard_report_data


@pytest.mark.parametrize("solution_count", [1, 25])
def test_report_data_preserves_export_fields_with_constant_query_count(db_sessionmaker, solution_count):
    unused_text = "Unused large text " * 1024
    project = {
        "project_id": "project", "program_id": "program", "project_name": "Project",
        "function": "Operations", "area": "Delivery", "description": "Project description",
        "status": "active", "sponsor": "Sponsor", "sponsor_user_soeid": "sp12345",
        "owner": "Project Owner", "owner_user_soeid": "po12345",
    }
    solution = {
        "project_id": "project", "description": "Solution description", "status": "on_hold",
        "planned_start_date": date(2026, 10, 1), "due_date": date(2026, 11, 30),
        "current_phase": "development", "escalation": "Needs approval",
        "owner": "Solution Owner", "owner_user_soeid": "so12345", "assignee": "Assignee",
        "key_stakeholder": "Stakeholder",
    }
    solutions = [
        {**solution, "solution_id": f"solution-{index:02d}", "solution_name": f"Solution {index:02d}"}
        for index in range(solution_count)
    ]
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", space_id="test-space", program_name="Program", description=unused_text))
        session.add(Project(**project, space_id="test-space", success_criteria=unused_text, strategic_objective=unused_text))
        session.add_all(
            Solution(
                **row, space_id="test-space", success_criteria=unused_text,
                problem_statement=unused_text, blockers=unused_text, risks=unused_text,
            )
            for row in reversed(solutions)
        )
        session.add_all([
            Phase(phase_id="development", phase_group="Development", phase_name="Development", sequence=3),
            Phase(phase_id="backlog", phase_group="Backlog", phase_name="Intake / Backlog", sequence=1),
            Phase(phase_id="legacy", phase_group="Legacy", phase_name="Legacy", sequence=2),
        ])
        session.commit()

    statements = []

    def capture_selects(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = db_sessionmaker.kw["bind"]
    event.listen(engine, "before_cursor_execute", capture_selects)
    try:
        with db_sessionmaker() as session:
            report = load_program_dashboard_report_data(
                session, space_id="test-space", selected_program_ids=[" program ", "", "program", "missing"],
            )
    finally:
        event.remove(engine, "before_cursor_execute", capture_selects)

    assert report == {
        "selected_program_label": "Program",
        "programs": [{"program_id": "program", "program_name": "Program"}],
        "projects": [project],
        "solutions": solutions,
        "phases": [
            {"phase_id": "backlog", "phase_name": "Intake / Backlog", "sequence": 1},
            {"phase_id": "development", "phase_name": "Development", "sequence": 3},
        ],
    }
    assert len(statements) == 4


def test_report_data_excludes_deleted_and_cross_space_descendants(db_sessionmaker):
    deleted_at = datetime.now(timezone.utc)
    with db_sessionmaker() as session:
        session.add_all([
            Program(program_id="visible", space_id="test-space", program_name="Visible"),
            Program(program_id="deleted", space_id="test-space", program_name="Deleted", deleted_at=deleted_at),
            Program(program_id="foreign", space_id="other-space", program_name="Foreign"),
            Program(program_id="unselected", space_id="test-space", program_name="Unselected"),
        ])
        session.add_all([
            Project(project_id="visible", space_id="test-space", program_id="visible", project_name="Visible"),
            Project(project_id="deleted", space_id="test-space", program_id="visible", project_name="Deleted", deleted_at=deleted_at),
            Project(project_id="foreign", space_id="other-space", program_id="visible", project_name="Foreign"),
            Project(project_id="deleted-parent", space_id="test-space", program_id="deleted", project_name="Deleted parent"),
            Project(project_id="foreign-parent", space_id="test-space", program_id="foreign", project_name="Foreign parent"),
            Project(project_id="unselected", space_id="test-space", program_id="unselected", project_name="Unselected"),
        ])
        session.add_all([
            Solution(solution_id="visible", space_id="test-space", project_id="visible", solution_name="Visible"),
            Solution(solution_id="deleted", space_id="test-space", project_id="visible", solution_name="Deleted", deleted_at=deleted_at),
            Solution(solution_id="foreign", space_id="other-space", project_id="visible", solution_name="Foreign"),
        ])
        session.add_all(
            Solution(solution_id=project_id, space_id="test-space", project_id=project_id, solution_name=project_id)
            for project_id in ("deleted-parent", "foreign-parent", "unselected")
        )
        session.add(Solution(solution_id="deleted-project", space_id="test-space", project_id="deleted", solution_name="Deleted project"))
        session.add(Solution(solution_id="foreign-project", space_id="test-space", project_id="foreign", solution_name="Foreign project"))
        session.commit()

    with db_sessionmaker() as session:
        report = load_program_dashboard_report_data(
            session, space_id="test-space", selected_program_ids=["visible", "deleted", "foreign"],
        )

    assert [row["program_id"] for row in report["programs"]] == ["visible"]
    assert [row["project_id"] for row in report["projects"]] == ["visible"]
    assert [row["solution_id"] for row in report["solutions"]] == ["visible"]
