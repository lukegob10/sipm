import pytest
from sqlalchemy import event

from backend.app.models import Program, Project
from backend.app.services.smart_cache import clear_cache


def _capture_selects(engine):
    statements = []

    def record_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_select)
    return statements, record_select


def _stop_capture(engine, listener):
    event.remove(engine, "before_cursor_execute", listener)


async def _create_task_graph(client):
    project_response = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Read Review Project"},
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    solution_response = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Read Review Solution",
            "github_repo_url": "https://github.com/example/read-review",
        },
    )
    assert solution_response.status_code == 201, solution_response.text
    solution = solution_response.json()

    task_response = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/tasks",
        json={"task_name": "Read Review Task"},
    )
    assert task_response.status_code == 201, task_response.text
    return solution, task_response.json()


@pytest.mark.anyio
async def test_project_list_does_not_expose_program_from_another_space(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all(
            [
                Program(
                    program_id="foreign-program",
                    space_id="foreign-space",
                    program_name="Confidential Foreign Program",
                ),
                Project(
                    project_id="cross-space-project",
                    space_id="test-space",
                    program_id="foreign-program",
                    project_name="Cross Space Project",
                ),
            ]
        )
        session.commit()

    response = await client.get("/project-manager/api/projects/")

    assert response.status_code == 200, response.text
    assert response.json() == []
    assert "Confidential Foreign Program" not in response.text


@pytest.mark.anyio
async def test_task_lists_include_solution_repo_with_one_list_query(client, db_sessionmaker):
    solution, task = await _create_task_graph(client)
    engine = db_sessionmaker.kw["bind"]

    clear_cache()
    by_solution_statements, by_solution_listener = _capture_selects(engine)
    try:
        by_solution = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/tasks"
        )
    finally:
        _stop_capture(engine, by_solution_listener)

    assert by_solution.status_code == 200, by_solution.text
    assert [row["task_id"] for row in by_solution.json()] == [task["task_id"]]
    assert by_solution.json()[0]["effective_github_repo_url"] == "https://github.com/example/read-review"
    assert len(by_solution_statements) == 2  # solution existence plus one joined task-list query

    clear_cache()
    all_tasks_statements, all_tasks_listener = _capture_selects(engine)
    try:
        all_tasks = await client.get("/project-manager/api/tasks")
    finally:
        _stop_capture(engine, all_tasks_listener)

    assert all_tasks.status_code == 200, all_tasks.text
    assert [row["task_id"] for row in all_tasks.json()] == [task["task_id"]]
    assert all_tasks.json()[0]["effective_github_repo_url"] == "https://github.com/example/read-review"
    assert len(all_tasks_statements) == 1


@pytest.mark.anyio
async def test_pm_report_does_not_query_unused_space_users(client, db_sessionmaker):
    await _create_task_graph(client)
    engine = db_sessionmaker.kw["bind"]
    statements, listener = _capture_selects(engine)
    try:
        response = await client.get("/project-manager/api/pm-dashboard/report.pdf")
    finally:
        _stop_capture(engine, listener)

    assert response.status_code == 200, response.text
    assert response.content.startswith(b"%PDF-")
    assert len(statements) == 3  # projects, solutions, and tasks
    assert all(".description as" not in statement.lower() for statement in statements)
