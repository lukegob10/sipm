import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, Task


@pytest.mark.anyio
async def test_pm_report_skips_unused_blocker_text_without_losing_blocked_items(
    client, db_sessionmaker
):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(space_id="test-space", name="Report Space", slug="report-space"),
                Program(program_id="program", space_id="test-space", program_name="Program"),
                Project(
                    project_id="project",
                    space_id="test-space",
                    program_id="program",
                    project_name="Delivery Project",
                ),
                Solution(
                    solution_id="solution",
                    space_id="test-space",
                    project_id="project",
                    solution_name="Delivery Workstream",
                    rag_status="red",
                    owner="Workstream Owner",
                ),
                Task(
                    task_id="task",
                    space_id="test-space",
                    project_id="project",
                    solution_id="solution",
                    task_name="Blocked Deliverable",
                    assignee="Delivery Owner",
                    blocked=True,
                    blocker_note="Unused report blocker explanation. " * 2000,
                ),
            ]
        )
        session.commit()

    statements = []
    engine = db_sessionmaker.kw["bind"]

    def capture_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture_select)
    try:
        response = await client.get("/project-manager/api/pm-dashboard/report.pdf")
    finally:
        event.remove(engine, "before_cursor_execute", capture_select)

    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
    assert b"Delivery Project" in response.content
    assert b"Delivery Workstream" in response.content
    assert b"Blocked Deliverable" in response.content
    assert b"Delivery Owner" in response.content
    assert b"Blocked deliverables 1" in response.content
    assert len(statements) == 3
    assert all(".blocker_note" not in statement for statement in statements)
