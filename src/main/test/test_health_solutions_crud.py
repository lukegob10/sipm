from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space
from backend.app.routes.solutions.common import _ensure_project_exists
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("project_id", ["active", "deleted", "foreign", "missing"])
def test_solution_parent_check_keeps_scope_without_loading_project_text(
    db_sessionmaker, project_id
):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="local", name="Local", slug="local"),
            Space(space_id="other", name="Other", slug="other"),
            Program(program_id="local-program", space_id="local", program_name="Local"),
            Program(program_id="other-program", space_id="other", program_name="Other"),
            Project(
                project_id="active", program_id="local-program", space_id="local",
                project_name="Active", description="Long parent description " * 1000,
            ),
            Project(
                project_id="deleted", program_id="local-program", space_id="local",
                project_name="Deleted", deleted_at=datetime.now(timezone.utc),
            ),
            Project(
                project_id="foreign", program_id="other-program", space_id="other",
                project_name="Foreign",
            ),
        ])
        session.commit()

    context = SpaceContext(
        space_id="local", space_name="Local", space_role="member", is_global_admin=False,
    )
    loaded = []
    with db_sessionmaker() as session:
        event.listen(session, "loaded_as_persistent", lambda _session, instance: loaded.append(instance))
        if project_id == "active":
            assert _ensure_project_exists(session, project_id, context) is None
        else:
            with pytest.raises(HTTPException) as error:
                _ensure_project_exists(session, project_id, context)
            assert error.value.status_code == 404
            assert error.value.detail == "Project not found"
        assert not any(isinstance(instance, Project) for instance in loaded)


@pytest.mark.anyio
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_solution_conflict_checks_do_not_load_unused_entities(client, operation):
    project_response = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Conflict Project", "description": "Parent text " * 1000},
    )
    assert project_response.status_code == 201, project_response.text
    project_id = project_response.json()["project_id"]
    create_path = f"/project-manager/api/projects/{project_id}/solutions"
    conflict_response = await client.post(
        create_path,
        json={"solution_name": "Taken", "version": "1", "description": "Solution text " * 1000},
    )
    assert conflict_response.status_code == 201, conflict_response.text
    source_id = None
    if operation == "update":
        source_response = await client.post(
            create_path, json={"solution_name": "Original", "version": "1"},
        )
        assert source_response.status_code == 201, source_response.text
        source_id = source_response.json()["solution_id"]

    loaded = []

    def record_project(instance, _context):
        loaded.append(("project", instance.project_id))

    def record_solution(instance, _context):
        loaded.append(("solution", instance.solution_id))

    event.listen(Project, "load", record_project)
    event.listen(Solution, "load", record_solution)
    try:
        if operation == "create":
            response = await client.post(
                create_path, json={"solution_name": "Taken", "version": "1"},
            )
        else:
            response = await client.patch(
                f"/project-manager/api/solutions/{source_id}",
                json={"solution_name": "Taken"},
            )
    finally:
        event.remove(Project, "load", record_project)
        event.remove(Solution, "load", record_solution)

    assert response.status_code == 400, response.text
    assert response.json()["detail"] == "Solution name and version already exist for this project"
    assert loaded == ([] if source_id is None else [("solution", source_id)])
    rows_response = await client.get(f"/project-manager/api/projects/{project_id}/solutions")
    assert rows_response.status_code == 200, rows_response.text
    assert {row["solution_name"] for row in rows_response.json()} == (
        {"Taken"} if operation == "create" else {"Taken", "Original"}
    )
