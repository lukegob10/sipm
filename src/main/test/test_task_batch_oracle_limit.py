import re
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, SpaceMembership, Task, User
from backend.app.routes.tasks import write as task_write
from backend.app.schemas import TaskBatchUpdate
from backend.app.services.spaces import SpaceContext


def test_committed_task_batch_publishes_if_refresh_fails(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        session.add(User(user_id="user", soeid="user", email="user@example.com", display_name="User", password_hash="unused", role="user", is_active=True))
        session.add(SpaceMembership(space_id="space", user_id="user", role="member", status="active"))
        session.add(Program(program_id="program", space_id="space", program_name="Program"))
        session.add(Project(project_id="project", program_id="program", space_id="space", project_name="Project"))
        session.add(Solution(solution_id="solution", project_id="project", space_id="space", solution_name="Solution"))
        session.add(Task(task_id="task", solution_id="solution", project_id="project", space_id="space", task_name="Task"))
        session.commit()
        published = []
        monkeypatch.setattr(task_write, "_publish_task_mutation", published.append)

        def fail_refresh(*_args, **_kwargs):
            raise RuntimeError("refresh failed")

        monkeypatch.setattr(session, "refresh", fail_refresh)
        with pytest.raises(RuntimeError, match="refresh failed"):
            task_write.batch_update_tasks(
                TaskBatchUpdate(task_ids=["task"], priority=1), session=session,
                current_user=SimpleNamespace(user_id="user"),
                space_ctx=SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member"),
            )
        assert published == ["space"]
    with db_sessionmaker() as session:
        assert session.get(Task, "task").priority == 1


@pytest.mark.anyio
async def test_task_batch_updates_and_returns_more_than_1000_solutions(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add(Program(program_id="program", space_id="test-space", program_name="Program"))
        session.add(Project(project_id="project", program_id="program", space_id="test-space", project_name="Project"))
        for index in range(1001):
            value = str(index)
            session.add(Solution(solution_id=f"solution-{value}", project_id="project", space_id="test-space",
                                 solution_name=f"Solution {value}", github_repo_url="https://github.com/example/shared"))
            session.add(Task(task_id=f"task-{value}", solution_id=f"solution-{value}", project_id="project",
                             space_id="test-space", task_name=f"Task {value}"))
        session.commit()

    engine = db_sessionmaker.kw["bind"]

    def enforce_oracle_limit(_connection, _cursor, statement, _parameters, _context, _executemany):
        for match in re.finditer(r"\bIN\s*\(([^)]*)\)", statement, flags=re.IGNORECASE):
            assert match.group(1).count("?") <= 1000, "Oracle IN list exceeds 1000 expressions"

    event.listen(engine, "before_cursor_execute", enforce_oracle_limit)
    try:
        response = await client.patch(
            "/project-manager/api/tasks/actions/batch",
            json={"task_ids": [f"task-{index}" for index in range(1001)], "priority": 1},
        )
    finally:
        event.remove(engine, "before_cursor_execute", enforce_oracle_limit)

    assert response.status_code == 200, response.text
    assert len(response.json()) == 1001
    assert all(row["priority"] == 1 for row in response.json())
    assert all(row["effective_github_repo_url"] == "https://github.com/example/shared" for row in response.json())
