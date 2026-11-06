from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, Task
from backend.app.routes.tasks.common import _solution_repo_map
from backend.app.services.spaces import SpaceContext


async def _create_task(client):
    project = await client.post(
        "/project-manager/api/projects/", json={"project_name": "Batch Assignment"}
    )
    assert project.status_code == 201, project.text
    solution = await client.post(
        f"/project-manager/api/projects/{project.json()['project_id']}/solutions",
        json={
            "solution_name": "Batch Assignment",
            "github_repo_url": "https://github.com/example/batch-assignment",
        },
    )
    assert solution.status_code == 201, solution.text
    task = await client.post(
        f"/project-manager/api/solutions/{solution.json()['solution_id']}/tasks",
        json={
            "task_name": "Find Assigned Task",
            "assignee": "Original User",
            "assignee_user_soeid": "original",
        },
    )
    assert task.status_code == 201, task.text
    return task.json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "assignee,soeid,expected_assignee,expected_soeid",
    [
        ("  Engineer Z\t", " ez99999 ", "Engineer Z", "ez99999"),
        (" \t ", "\t ", "", None),
    ],
)
async def test_batch_assignment_normalizes_labels_and_identity(
    client, db_sessionmaker, assignee, soeid, expected_assignee, expected_soeid
):
    task = await _create_task(client)
    response = await client.patch(
        "/project-manager/api/tasks/actions/batch",
        json={
            "task_ids": [task["task_id"]],
            "assignee": assignee,
            "assignee_user_soeid": soeid,
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()[0]
    # Oracle persists an empty assignee label as NULL.
    assert (updated["assignee"] or "") == expected_assignee
    assert updated["assignee_user_soeid"] == expected_soeid
    assert updated["effective_github_repo_url"] == "https://github.com/example/batch-assignment"

    with db_sessionmaker() as session:
        persisted = session.get(Task, task["task_id"])
        assert (persisted.assignee or "") == expected_assignee
        assert persisted.assignee_user_soeid == expected_soeid

    if expected_assignee:
        for filters in (
            {"assignee": expected_assignee},
            {"assignee_user_soeid": expected_soeid},
        ):
            result = await client.get("/project-manager/api/tasks", params=filters)
            assert result.status_code == 200, result.text
            assert [row["task_id"] for row in result.json()] == [task["task_id"]]


def test_solution_repo_lookup_deduplicates_ids_and_reads_only_repo_columns(db_sessionmaker):
    ctx = SpaceContext(
        space_id="test-space", space_name="Test", is_global_admin=False, space_role="member"
    )
    with db_sessionmaker() as session:
        session.add_all(
            [
                Space(space_id=ctx.space_id, name="Test", slug="task-crud-health"),
                Space(space_id="another-space", name="Other", slug="task-crud-health-other"),
                Program(program_id="program", space_id=ctx.space_id, program_name="Program"),
                Project(
                    project_id="project", program_id="program", space_id=ctx.space_id,
                    project_name="Project",
                ),
                Solution(
                    solution_id="solution", project_id="project", space_id=ctx.space_id,
                    solution_name="Solution", github_repo_url="https://github.com/example/repo",
                ),
                Solution(
                    solution_id="deleted", project_id="project", space_id=ctx.space_id,
                    solution_name="Deleted", deleted_at=datetime.now(timezone.utc),
                ),
                Solution(
                    solution_id="foreign", project_id="project", space_id="another-space",
                    solution_name="Foreign",
                ),
            ]
        )
        session.commit()
        queries = []
        engine = db_sessionmaker.kw["bind"]

        def record_select(_connection, cursor, statement, parameters, _context, _executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                values = list(parameters.values()) if isinstance(parameters, dict) else list(parameters)
                queries.append((values, len(cursor.description)))

        event.listen(engine, "after_cursor_execute", record_select)
        try:
            result = _solution_repo_map(
                session, ctx, ["solution"] * 1201 + ["deleted", "foreign", ""]
            )
        finally:
            event.remove(engine, "after_cursor_execute", record_select)

        assert result == {"solution": "https://github.com/example/repo"}
        assert len(queries) == 1
        values, column_count = queries[0]
        assert values.count("solution") == 1
        assert column_count == 2
