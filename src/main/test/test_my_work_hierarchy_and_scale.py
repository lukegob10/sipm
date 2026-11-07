import re
from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Task
from backend.app.services.agent_assigned_work import list_agent_assigned_work
from backend.app.services.agent_work_graph import build_work_graph
from backend.app.services.spaces import SpaceContext


@pytest.mark.anyio
async def test_agent_and_my_work_match_trimmed_assignee_identity(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            Program(program_id="program", space_id="test-space", program_name="Program"),
            Project(project_id="project", program_id="program", space_id="test-space", project_name="Project"),
            Solution(solution_id="solution", project_id="project", space_id="test-space", solution_name="Solution"),
            Task(task_id="task", project_id="project", solution_id="solution", space_id="test-space",
                 task_name="Task", assignee_user_soeid=" TU12345 "),
        ])
        session.commit()
        agent_work = list_agent_assigned_work(
            session, SpaceContext(space_id="test-space", space_name="Test", is_global_admin=False, space_role="member"),
            assignee_user_soeid="tu12345", cursor=None, limit=50,
        )
        assert [item.task.task_id for item in agent_work.records] == ["task"]
    work = await client.get("/project-manager/api/my-work")
    assert work.status_code == 200, work.text
    assert [item["task"]["task_id"] for item in work.json()] == ["task"]


@pytest.mark.anyio
@pytest.mark.parametrize("hidden_program", ["deleted", "other-space"])
async def test_my_work_and_repositories_exclude_hidden_program_hierarchy(client, db_sessionmaker, hidden_program):
    with db_sessionmaker() as session:
        session.add(Program(
            program_id="hidden-program", program_name="Hidden",
            space_id="other-space" if hidden_program == "other-space" else "test-space",
            deleted_at=datetime.now(timezone.utc) if hidden_program == "deleted" else None,
        ))
        session.add(Project(project_id="project", program_id="hidden-program", space_id="test-space", project_name="Project"))
        session.add(Solution(solution_id="solution", project_id="project", space_id="test-space", solution_name="Solution",
                             github_repo_url="https://github.com/example/hidden"))
        session.add(Task(task_id="task", project_id="project", solution_id="solution", space_id="test-space",
                         task_name="Task", assignee_user_soeid="tu12345"))
        session.commit()
        agent_work = list_agent_assigned_work(
            session, SpaceContext(space_id="test-space", space_name="Test", is_global_admin=False, space_role="member"),
            assignee_user_soeid="tu12345", cursor=None, limit=50,
        )
        assert agent_work.records == []
        graph = build_work_graph(
            session, SpaceContext(space_id="test-space", space_name="Test", is_global_admin=False, space_role="member")
        )
        assert graph.records == []

    work = await client.get("/project-manager/api/my-work")
    assert work.status_code == 200, work.text
    assert work.json() == []
    inventory = await client.get("/project-manager/api/repository-inventory")
    assert inventory.status_code == 200, inventory.text
    assert inventory.json() == []


@pytest.mark.anyio
async def test_my_work_and_repositories_ignore_mismatched_task_hierarchy(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", space_id="test-space", program_name="Program"))
        session.add(Project(project_id="project", program_id="program", space_id="test-space", project_name="Project"))
        session.add(Solution(solution_id="solution", project_id="project", space_id="test-space", solution_name="Solution"))
        session.add(Task(task_id="mismatch", project_id="missing-project", solution_id="solution", space_id="test-space",
                         task_name="Mismatch", assignee_user_soeid="tu12345", github_repo_url="https://github.com/example/mismatch"))
        session.commit()

    work = await client.get("/project-manager/api/my-work")
    assert work.status_code == 200, work.text
    assert work.json() == []
    state = await client.patch("/project-manager/api/my-work/tasks/mismatch/state", json={"bucket": "today"})
    assert state.status_code == 404
    inventory = await client.get("/project-manager/api/repository-inventory")
    assert inventory.status_code == 200, inventory.text
    assert inventory.json() == []


@pytest.mark.anyio
async def test_my_work_and_repository_queries_handle_oracle_in_limit(client, db_sessionmaker):
    with db_sessionmaker() as session:
        for index in range(1001):
            value = str(index)
            session.add(Program(program_id=f"program-{value}", space_id="test-space", program_name=f"Program {value}"))
            session.add(Project(project_id=f"project-{value}", program_id=f"program-{value}",
                                space_id="test-space", project_name=f"Project {value}"))
            session.add(Solution(solution_id=f"solution-{value}", project_id=f"project-{value}",
                                 space_id="test-space", solution_name=f"Solution {value}",
                                 github_repo_url="https://github.com/example/shared"))
            session.add(Task(task_id=f"task-{value}", solution_id=f"solution-{value}", project_id=f"project-{value}",
                             space_id="test-space", task_name=f"Task {value}", assignee_user_soeid="tu12345"))
        session.commit()

    engine = db_sessionmaker.kw["bind"]

    def enforce_oracle_limit(_connection, _cursor, statement, _parameters, _context, _executemany):
        for match in re.finditer(r"\bIN\s*\(([^)]*)\)", statement, flags=re.IGNORECASE):
            assert match.group(1).count("?") <= 1000, "Oracle IN list exceeds 1000 expressions"

    event.listen(engine, "before_cursor_execute", enforce_oracle_limit)
    try:
        work = await client.get("/project-manager/api/my-work")
        assert work.status_code == 200, work.text
        assert len(work.json()) == 1001
        inventory = await client.get("/project-manager/api/repository-inventory")
        assert inventory.status_code == 200, inventory.text
        assert inventory.json()[0]["task_count"] == 1001
    finally:
        event.remove(engine, "before_cursor_execute", enforce_oracle_limit)
