from __future__ import annotations

import csv
from datetime import datetime, timezone
from io import StringIO

import pytest
from sqlalchemy import event

from backend.app.models import Phase, Program, Project, Solution, SolutionPhase, Space


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("disabled_phases", [(), ("requirements",), ("backlog", "requirements")])
async def test_solution_import_preview_matches_enabled_phase_validation(
    client, db_sessionmaker, dry_run, disabled_phases
):
    with db_sessionmaker() as session:
        session.add_all([
            Phase(phase_id="backlog", phase_group="Backlog", phase_name="Backlog", sequence=1),
            Phase(phase_id="requirements", phase_group="Planning", phase_name="Requirements", sequence=2),
        ])
        session.commit()
    project_response = await client.post(
        "/project-manager/api/projects/", json={"project_name": "Import Phase Project"}
    )
    assert project_response.status_code == 201, project_response.text
    solution_response = await client.post(
        f"/project-manager/api/projects/{project_response.json()['project_id']}/solutions",
        json={"solution_name": "Existing", "description": "Original", "current_phase": "backlog"},
    )
    assert solution_response.status_code == 201, solution_response.text
    solution_id = solution_response.json()["solution_id"]
    with db_sessionmaker() as session:
        for phase in session.query(SolutionPhase).filter_by(solution_id=solution_id):
            phase.is_enabled = phase.phase_id not in disabled_phases
        session.commit()

    response = await client.post(
        f"/project-manager/api/solutions/import?dry_run={str(dry_run).lower()}",
        content=(
            "project_name,solution_name,current_phase,description\n"
            "Import Phase Project,Existing,requirements,Changed\n"
            "Import Phase Project,Later,backlog,Later description\n"
        ),
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 1
    assert result["updated"] == (0 if disabled_phases else 1)
    assert result["projects_created"] == 0
    assert result["total_rows"] == 2
    if len(disabled_phases) == 2:
        assert result["errors"] == [
            "Row 2: 400: No phases enabled for this solution; current_phase must be null"
        ]
    elif disabled_phases:
        assert result["errors"] == [
            "Row 2: 400: current_phase must be one of the enabled phases for this solution"
        ]
    else:
        assert result["errors"] == []
    with db_sessionmaker() as session:
        existing = session.get(Solution, solution_id)
        applied = not dry_run and not disabled_phases
        assert existing.description == ("Changed" if applied else "Original")
        assert existing.current_phase == ("requirements" if applied else "backlog")
        later = session.query(Solution).filter_by(solution_name="Later").first()
        assert (later is None) is dry_run


@pytest.mark.anyio
@pytest.mark.parametrize("solution_count", [0, 3])
async def test_solution_export_uses_joined_project_names_and_preserves_scope(
    client, db_sessionmaker, solution_count
):
    now = datetime.now(timezone.utc)
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="test-space", name="Test Space", slug="test-space"),
            Space(space_id="other-space", name="Other Space", slug="other-space"),
            Program(program_id="export-program", space_id="test-space", program_name="Export Program"),
            Program(program_id="foreign-program", space_id="other-space", program_name="Foreign Program"),
            Project(project_id="visible", space_id="test-space", program_id="export-program", project_name="Visible Project"),
            Project(project_id="empty", space_id="test-space", program_id="export-program", project_name="Empty Project", description="Unused project text"),
            Project(project_id="deleted", space_id="test-space", program_id="export-program", project_name="Deleted Project", deleted_at=now),
            Project(project_id="foreign", space_id="other-space", program_id="foreign-program", project_name="Foreign Project"),
        ])
        session.flush()
        session.add_all([
            Solution(solution_id="deleted-solution", project_id="visible", space_id="test-space", solution_name="Deleted", deleted_at=now),
            Solution(solution_id="deleted-parent", project_id="deleted", space_id="test-space", solution_name="Deleted parent"),
            Solution(solution_id="foreign-solution", project_id="foreign", space_id="other-space", solution_name="Foreign"),
            Solution(solution_id="foreign-parent", project_id="foreign", space_id="test-space", solution_name="Foreign parent"),
            Solution(solution_id="foreign-child", project_id="visible", space_id="other-space", solution_name="Foreign child"),
        ])
        for index in range(solution_count):
            session.add(Solution(
                solution_id=f"visible-{index}", project_id="visible", space_id="test-space",
                solution_name=f"Visible {index}", description="Line one,\nLine two", rag_confidence=0,
            ))
        session.commit()

    statements = []
    engine = db_sessionmaker.kw["bind"]

    def capture_select(_connection, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = await client.get("/project-manager/api/solutions/export")
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"] == 'attachment; filename="solutions.csv"'
    rows = list(csv.DictReader(StringIO(response.text)))
    assert {row["solution_name"] for row in rows} == {f"Visible {index}" for index in range(solution_count)}
    assert all(row["project_name"] == "Visible Project" for row in rows)
    assert all(row["description"] == "Line one,\nLine two" for row in rows)
    assert all(float(row["rag_confidence"]) == 0 for row in rows)
    assert len(statements) == 1, f"Solution export issued {len(statements)} SELECTs"
