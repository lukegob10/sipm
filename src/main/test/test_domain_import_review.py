from __future__ import annotations

import csv
from datetime import datetime, timezone

import pytest

from backend.app.models import Project, Solution, Task


async def create_project(client, name: str):
    response = await client.post("/project-manager/api/projects/", json={"project_name": name})
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


def mark_deleted_without_renaming(db_sessionmaker, model, record_id: str, id_field: str):
    with db_sessionmaker() as session:
        row = session.query(model).filter(getattr(model, id_field) == record_id).one()
        row.deleted_at = datetime.now(timezone.utc)
        session.commit()


@pytest.mark.anyio
@pytest.mark.parametrize("rag_confidence", ["NaN", "Infinity", "-Infinity", "1e9999"])
async def test_solution_import_rejects_non_finite_rag_confidence(client, rag_confidence):
    project_resp = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Finite Confidence Project"},
    )
    assert project_resp.status_code == 201, project_resp.text

    csv_text = "project_name,solution_name,rag_confidence\n"
    csv_text += f"Finite Confidence Project,Invalid Confidence Solution,{rag_confidence}\n"
    response = await client.post(
        "/project-manager/api/solutions/import",
        content=csv_text.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 0
    assert len(payload["errors"]) == 1
    assert "rag_confidence must be finite" in payload["errors"][0]

    solutions = await client.get("/project-manager/api/solutions")
    assert solutions.status_code == 200, solutions.text
    assert solutions.json() == []


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("path", "header", "row", "created_key"),
    [
        (
            "/project-manager/api/projects/import",
            "project_name,priority",
            "Malformed Project,3,unexpected",
            "created",
        ),
        (
            "/project-manager/api/solutions/import",
            "project_name,solution_name,priority",
            "Malformed Project,Malformed Solution,3,unexpected",
            "created",
        ),
        (
            "/project-manager/api/tasks/import",
            "project_name,solution_name,task_name,priority",
            "Malformed Project,Malformed Solution,Malformed Task,3,unexpected",
            "created",
        ),
    ],
)
async def test_imports_reject_rows_with_extra_csv_columns(
    client, path, header, row, created_key
):
    response = await client.post(
        path,
        content=f"{header}\n{row}\n".encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload[created_key] == 0
    assert len(payload["errors"]) == 1
    assert "too many columns" in payload["errors"][0]


@pytest.mark.anyio
async def test_project_import_releases_legacy_deleted_unique_key(client, db_sessionmaker):
    original = await create_project(client, "Legacy Import Project")
    mark_deleted_without_renaming(db_sessionmaker, Project, original["project_id"], "project_id")

    response = await client.post(
        "/project-manager/api/projects/import",
        content=b"project_name,priority\nLegacy Import Project,2\n",
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 1
    assert payload["errors"] == []


@pytest.mark.anyio
async def test_solution_import_releases_legacy_deleted_unique_key(client, db_sessionmaker):
    project = await create_project(client, "Legacy Import Solution Project")
    original = await create_solution(client, project["project_id"], "Legacy Import Solution")
    mark_deleted_without_renaming(db_sessionmaker, Solution, original["solution_id"], "solution_id")

    response = await client.post(
        "/project-manager/api/solutions/import",
        content=(
            "project_name,solution_name,version\n"
            "Legacy Import Solution Project,Legacy Import Solution,1.0.0\n"
        ).encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 1
    assert payload["errors"] == []


@pytest.mark.anyio
async def test_task_import_releases_legacy_deleted_unique_key(client, db_sessionmaker):
    project = await create_project(client, "Legacy Import Task Project")
    solution = await create_solution(client, project["project_id"], "Legacy Import Task Solution")
    original = await create_task(client, solution["solution_id"], "Legacy Import Task")
    mark_deleted_without_renaming(db_sessionmaker, Task, original["task_id"], "task_id")

    response = await client.post(
        "/project-manager/api/tasks/import",
        content=(
            "project_name,solution_name,version,task_name\n"
            "Legacy Import Task Project,Legacy Import Task Solution,1.0.0,Legacy Import Task\n"
        ).encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 1
    assert payload["errors"] == []


@pytest.mark.anyio
async def test_task_import_rejects_malformed_blocked_values(client):
    response = await client.post(
        "/project-manager/api/tasks/import",
        content=(
            "project_name,solution_name,task_name,blocked\n"
            "Malformed Boolean Project,Malformed Boolean Solution,Malformed Boolean Task,perhaps\n"
        ).encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 0
    assert len(payload["errors"]) == 1
    assert "blocked must be a boolean" in payload["errors"][0]


@pytest.mark.anyio
async def test_project_import_rejects_unterminated_csv_quote(client):
    response = await client.post(
        "/project-manager/api/projects/import",
        content=(
            b"project_name,priority\n\"Broken Project,2\n"
            b"Second Project,3\n"
        ),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 0
    assert payload["total_rows"] == 0
    assert len(payload["errors"]) == 1
    assert "Invalid CSV" in payload["errors"][0]


@pytest.mark.anyio
async def test_project_import_rejects_oversized_csv_field_without_server_error(client):
    oversized_field = "x" * (csv.field_size_limit() + 1)
    csv_text = f"project_name,description\nOversized CSV Project,{oversized_field}\n"
    response = await client.post(
        "/project-manager/api/projects/import",
        content=csv_text.encode("utf-8"),
        headers={"Content-Type": "text/csv"},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["created"] == 0
    assert payload["total_rows"] == 0
    assert len(payload["errors"]) == 1
    assert "Invalid CSV" in payload["errors"][0]
