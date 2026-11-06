from datetime import datetime, timezone
import re

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Task
from backend.app.routes import pm_dashboard


@pytest.mark.anyio
async def test_pm_report_handles_large_spaces_and_excludes_hidden_hierarchies(client, db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        session.add_all([
            Program(program_id="visible", space_id="test-space", program_name="Visible"),
            Program(program_id="archived", space_id="test-space", program_name="Archived",
                    deleted_at=datetime.now(timezone.utc)),
            Program(program_id="foreign", space_id="other-space", program_name="Foreign"),
        ])
        for index in range(1001):
            key = str(index)
            session.add(Project(project_id=f"p{key}", space_id="test-space", program_id="visible", project_name=f"P {key}"))
            session.add(Solution(solution_id=f"s{key}", space_id="test-space", project_id=f"p{key}", solution_name=f"S {key}"))
        for key, program_id in [("archived", "archived"), ("foreign", "foreign")]:
            session.add(Project(project_id=key, space_id="test-space", program_id=program_id, project_name=key))
            session.add(Solution(solution_id=key, space_id="test-space", project_id=key, solution_name=key))
            session.add(Task(task_id=key, space_id="test-space", project_id=key, solution_id=key, task_name=key))
        session.add(Task(task_id="valid", space_id="test-space", project_id="p0", solution_id="s0", task_name="Valid"))
        session.add(Task(task_id="mismatch", space_id="test-space", project_id="p1", solution_id="s0", task_name="Mismatch"))
        session.commit()

    captured = {}
    monkeypatch.setattr(pm_dashboard, "build_pm_command_report_pdf", lambda **kwargs: captured.update(kwargs) or b"%PDF-1.4")
    engine = db_sessionmaker.kw["bind"]

    def enforce_oracle_limit(_connection, _cursor, statement, _parameters, _context, _executemany):
        for match in re.finditer(r"\bIN\s*\(([^)]*)\)", statement, flags=re.IGNORECASE):
            assert match.group(1).count("?") <= 1000, "Oracle IN list exceeds 1000 expressions"

    event.listen(engine, "before_cursor_execute", enforce_oracle_limit)
    try:
        response = await client.get("/project-manager/api/pm-dashboard/report.pdf")
    finally:
        event.remove(engine, "before_cursor_execute", enforce_oracle_limit)
    assert response.status_code == 200, response.text
    assert len(captured["projects"]) == 1001
    assert len(captured["solutions"]) == 1001
    assert [row["task_id"] for row in captured["tasks"]] == ["valid"]
