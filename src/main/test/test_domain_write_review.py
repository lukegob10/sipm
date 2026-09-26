from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.models import Project, Solution, Task


async def create_project(client, name: str):
    response = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_solution(client, project_id: str, name: str):
    response = await client.post(
        f"/project-manager/api/projects/{project_id}/solutions",
        json={"solution_name": name, "version": "1.0.0"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def create_task(client, solution_id: str, name: str):
    response = await client.post(
        f"/project-manager/api/solutions/{solution_id}/tasks",
        json={"task_name": name},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
@pytest.mark.parametrize("entity", ["project", "solution", "task"])
async def test_renaming_live_row_releases_legacy_deleted_name(
    client, db_sessionmaker, entity
):
    if entity == "project":
        original = await create_project(client, "Legacy Rename Target")
        live = await create_project(client, "Live Project")
        model, id_field, record_id = Project, "project_id", original["project_id"]
        path = f"/project-manager/api/projects/{live['project_id']}"
        field = "project_name"
        live_id_field = "project_id"
    elif entity == "solution":
        project = await create_project(client, "Legacy Rename Solution Project")
        original = await create_solution(
            client, project["project_id"], "Legacy Rename Target"
        )
        live = await create_solution(client, project["project_id"], "Live Solution")
        model, id_field, record_id = Solution, "solution_id", original["solution_id"]
        path = f"/project-manager/api/solutions/{live['solution_id']}"
        field = "solution_name"
        live_id_field = "solution_id"
    else:
        project = await create_project(client, "Legacy Rename Task Project")
        solution = await create_solution(
            client, project["project_id"], "Legacy Rename Task Solution"
        )
        original = await create_task(client, solution["solution_id"], "Legacy Rename Target")
        live = await create_task(client, solution["solution_id"], "Live Task")
        model, id_field, record_id = Task, "task_id", original["task_id"]
        path = f"/project-manager/api/tasks/{live['task_id']}"
        field = "task_name"
        live_id_field = "task_id"

    with db_sessionmaker() as session:
        old_row = session.query(model).filter(getattr(model, id_field) == record_id).one()
        old_row.deleted_at = datetime.now(timezone.utc)
        session.commit()

    response = await client.patch(path, json={field: "Legacy Rename Target"})
    assert response.status_code == 200, response.text
    assert response.json()[field] == "Legacy Rename Target"

    with db_sessionmaker() as session:
        old_row = session.query(model).filter(getattr(model, id_field) == record_id).one()
        updated_row = (
            session.query(model)
            .filter(getattr(model, live_id_field) == live[live_id_field])
            .one()
        )
        assert old_row.deleted_at is not None
        assert old_row is not updated_row
        assert updated_row.deleted_at is None
        assert getattr(updated_row, field) == "Legacy Rename Target"


@pytest.mark.anyio
async def test_deleting_solution_releases_name_for_recreate(client, db_sessionmaker):
    project = await create_project(client, "Reusable Solution Project")
    original = await create_solution(client, project["project_id"], "Reusable Solution")

    deleted = await client.delete(
        f"/project-manager/api/solutions/{original['solution_id']}"
    )
    assert deleted.status_code == 204, deleted.text

    recreated = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Reusable Solution", "version": "1.0.0"},
    )
    assert recreated.status_code == 201, recreated.text

    with db_sessionmaker() as session:
        old_row = session.query(Solution).filter_by(solution_id=original["solution_id"]).one()
        assert old_row.deleted_at is not None
        assert old_row.solution_name != "Reusable Solution"
        assert "[deleted " in old_row.solution_name
        assert len(old_row.solution_name) <= 255
    assert recreated.json()["solution_name"] == "Reusable Solution"


@pytest.mark.anyio
async def test_deleting_task_releases_name_for_recreate(client, db_sessionmaker):
    project = await create_project(client, "Reusable Task Project")
    solution = await create_solution(client, project["project_id"], "Reusable Task Solution")
    original = await create_task(client, solution["solution_id"], "Reusable Task")

    deleted = await client.delete(f"/project-manager/api/tasks/{original['task_id']}")
    assert deleted.status_code == 204, deleted.text

    recreated = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/tasks",
        json={"task_name": "Reusable Task"},
    )
    assert recreated.status_code == 201, recreated.text

    with db_sessionmaker() as session:
        old_row = session.query(Task).filter_by(task_id=original["task_id"]).one()
        assert old_row.deleted_at is not None
        assert old_row.task_name != "Reusable Task"
        assert "[deleted " in old_row.task_name
        assert len(old_row.task_name) <= 255
    assert recreated.json()["task_name"] == "Reusable Task"


@pytest.mark.anyio
async def test_solution_create_releases_legacy_deleted_unique_key(client, db_sessionmaker):
    project = await create_project(client, "Legacy Deleted Solution Project")
    original = await create_solution(client, project["project_id"], "Legacy Solution")
    with db_sessionmaker() as session:
        old_row = session.query(Solution).filter_by(solution_id=original["solution_id"]).one()
        old_row.deleted_at = datetime.now(timezone.utc)
        session.commit()

    recreated = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Legacy Solution", "version": "1.0.0"},
    )
    assert recreated.status_code == 201, recreated.text


@pytest.mark.anyio
async def test_task_create_releases_legacy_deleted_unique_key(client, db_sessionmaker):
    project = await create_project(client, "Legacy Deleted Task Project")
    solution = await create_solution(client, project["project_id"], "Legacy Task Solution")
    original = await create_task(client, solution["solution_id"], "Legacy Task")
    with db_sessionmaker() as session:
        old_row = session.query(Task).filter_by(task_id=original["task_id"]).one()
        old_row.deleted_at = datetime.now(timezone.utc)
        session.commit()

    recreated = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/tasks",
        json={"task_name": "Legacy Task"},
    )
    assert recreated.status_code == 201, recreated.text


@pytest.mark.anyio
async def test_moving_solution_moves_tasks_and_invalidates_project_task_lists(client):
    project_a = await create_project(client, "Move Solution From")
    project_b = await create_project(client, "Move Solution To")
    solution = await create_solution(client, project_a["project_id"], "Moved Solution")
    task = await create_task(client, solution["solution_id"], "Moved Task")

    primed_destination = await client.get(
        "/project-manager/api/tasks",
        params={"project_id": project_b["project_id"]},
    )
    assert primed_destination.status_code == 200, primed_destination.text
    assert primed_destination.json() == []

    moved = await client.patch(
        f"/project-manager/api/solutions/{solution['solution_id']}",
        json={"project_id": project_b["project_id"]},
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["project_id"] == project_b["project_id"]

    destination_tasks = await client.get(
        "/project-manager/api/tasks",
        params={"project_id": project_b["project_id"]},
    )
    assert destination_tasks.status_code == 200, destination_tasks.text
    assert [row["task_id"] for row in destination_tasks.json()] == [task["task_id"]]
    assert destination_tasks.json()[0]["project_id"] == project_b["project_id"]

    source_tasks = await client.get(
        "/project-manager/api/tasks",
        params={"project_id": project_a["project_id"]},
    )
    assert source_tasks.status_code == 200, source_tasks.text
    assert source_tasks.json() == []

    deleted_source = await client.delete(
        f"/project-manager/api/projects/{project_a['project_id']}"
    )
    assert deleted_source.status_code == 204, deleted_source.text

    destination_tasks = await client.get(
        "/project-manager/api/tasks",
        params={"project_id": project_b["project_id"]},
    )
    assert destination_tasks.status_code == 200, destination_tasks.text
    assert [row["task_id"] for row in destination_tasks.json()] == [task["task_id"]]
