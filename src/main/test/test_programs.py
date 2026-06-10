import pytest


@pytest.mark.anyio
async def test_program_crud_and_delete_blocked_with_active_projects(client):
    create = await client.post(
        "/project-manager/api/programs",
        json={"program_name": "Transformation", "description": "Portfolio umbrella"},
    )
    assert create.status_code == 201, create.text
    program = create.json()
    assert program["program_name"] == "Transformation"

    project = await client.post(
        "/project-manager/api/projects",
        json={"program_id": program["program_id"], "project_name": "Program Project"},
    )
    assert project.status_code == 201, project.text
    assert project.json()["program_id"] == program["program_id"]
    assert project.json()["program_name"] == "Transformation"

    blocked = await client.delete(f"/project-manager/api/programs/{program['program_id']}")
    assert blocked.status_code == 400
    assert "active projects" in blocked.json()["detail"]

    update = await client.patch(
        f"/project-manager/api/programs/{program['program_id']}",
        json={"description": "Updated umbrella"},
    )
    assert update.status_code == 200, update.text
    assert update.json()["description"] == "Updated umbrella"


@pytest.mark.anyio
async def test_project_can_be_reassigned_between_programs(client):
    first = (
        await client.post("/project-manager/api/programs", json={"program_name": "First Program"})
    ).json()
    second = (
        await client.post("/project-manager/api/programs", json={"program_name": "Second Program"})
    ).json()
    project = (
        await client.post(
            "/project-manager/api/projects",
            json={"program_id": first["program_id"], "project_name": "Movable Project"},
        )
    ).json()

    reassigned = await client.patch(
        f"/project-manager/api/projects/{project['project_id']}",
        json={"program_id": second["program_id"]},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["program_id"] == second["program_id"]
    assert reassigned.json()["program_name"] == "Second Program"

    projects = await client.get(f"/project-manager/api/projects?program_id={second['program_id']}")
    assert projects.status_code == 200, projects.text
    assert [row["project_id"] for row in projects.json()] == [project["project_id"]]


@pytest.mark.anyio
async def test_project_reassignment_rejects_cross_space_program(client):
    program = (
        await client.post("/project-manager/api/programs", json={"program_name": "Visible Program"})
    ).json()
    project = (
        await client.post(
            "/project-manager/api/projects",
            json={"program_id": program["program_id"], "project_name": "Scoped Project"},
        )
    ).json()

    missing = await client.patch(
        f"/project-manager/api/projects/{project['project_id']}",
        json={"program_id": "not-in-this-space"},
    )
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Program not found"
