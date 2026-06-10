from __future__ import annotations

import pytest

from backend.app import deps as deps_module
from backend.app.models import SolutionDocument
from backend.app.routes.solutions import documents as solution_documents_route
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


async def create_solution(client, project_name: str = "Document Project"):
    project_resp = await client.post("/project-manager/api/projects/", json={"project_name": project_name})
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()
    solution_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Documented Solution"},
    )
    assert solution_resp.status_code == 201, solution_resp.text
    return solution_resp.json()


async def upload_document(client, solution_id: str, *, name: str = "notes.txt", content: bytes = b"hello"):
    return await client.post(
        f"/project-manager/api/solutions/{solution_id}/documents",
        files={"file": (name, content, "text/plain")},
    )


@pytest.mark.anyio
async def test_solution_document_upload_list_download_and_delete(client):
    solution = await create_solution(client)

    upload_resp = await upload_document(
        client,
        solution["solution_id"],
        name="requirements.txt",
        content=b"document body",
    )
    assert upload_resp.status_code == 201, upload_resp.text
    uploaded = upload_resp.json()
    assert uploaded["filename"] == "requirements.txt"
    assert uploaded["content_type"] == "text/plain"
    assert uploaded["size_bytes"] == len(b"document body")
    assert uploaded["uploaded_by_user_id"] == "test-user"
    assert "content" not in uploaded

    list_resp = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/documents")
    assert list_resp.status_code == 200, list_resp.text
    rows = list_resp.json()
    assert [row["document_id"] for row in rows] == [uploaded["document_id"]]
    assert all("content" not in row for row in rows)

    download_resp = await client.get(
        f"/project-manager/api/solutions/{solution['solution_id']}/documents/{uploaded['document_id']}/download"
    )
    assert download_resp.status_code == 200, download_resp.text
    assert download_resp.content == b"document body"
    assert "text/plain" in download_resp.headers.get("content-type", "")
    assert "attachment;" in download_resp.headers.get("content-disposition", "")
    assert "requirements.txt" in download_resp.headers.get("content-disposition", "")

    delete_resp = await client.delete(
        f"/project-manager/api/solutions/{solution['solution_id']}/documents/{uploaded['document_id']}"
    )
    assert delete_resp.status_code == 204, delete_resp.text

    list_after_delete = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/documents")
    assert list_after_delete.status_code == 200, list_after_delete.text
    assert list_after_delete.json() == []

    missing_download = await client.get(
        f"/project-manager/api/solutions/{solution['solution_id']}/documents/{uploaded['document_id']}/download"
    )
    assert missing_download.status_code == 404, missing_download.text


@pytest.mark.anyio
async def test_solution_document_upload_rejects_missing_solution_and_oversized_file(client, monkeypatch):
    missing_resp = await upload_document(client, "does-not-exist")
    assert missing_resp.status_code == 404, missing_resp.text

    solution = await create_solution(client, project_name="Oversized Document Project")
    monkeypatch.setattr(solution_documents_route, "MAX_SOLUTION_DOCUMENT_BYTES", 4)
    oversized = await upload_document(client, solution["solution_id"], content=b"12345")
    assert oversized.status_code == 413, oversized.text
    assert oversized.json()["detail"] == "Document exceeds the 25 MB limit"


@pytest.mark.anyio
async def test_solution_documents_are_space_scoped(client):
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-documents-a",
            space_name="Documents A",
            is_global_admin=False,
            space_role="space_admin",
        )
        solution = await create_solution(client, project_name="Scoped Document Project")
        upload_resp = await upload_document(client, solution["solution_id"])
        assert upload_resp.status_code == 201, upload_resp.text

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-documents-b",
            space_name="Documents B",
            is_global_admin=False,
            space_role="space_admin",
        )
        list_resp = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/documents")
        assert list_resp.status_code == 404, list_resp.text
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


@pytest.mark.anyio
async def test_solution_documents_become_unreachable_after_solution_delete(client, db_sessionmaker):
    solution = await create_solution(client, project_name="Deleted Solution Document Project")
    upload_resp = await upload_document(client, solution["solution_id"])
    assert upload_resp.status_code == 201, upload_resp.text
    document_id = upload_resp.json()["document_id"]

    delete_solution = await client.delete(f"/project-manager/api/solutions/{solution['solution_id']}")
    assert delete_solution.status_code == 204, delete_solution.text

    list_resp = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/documents")
    assert list_resp.status_code == 404, list_resp.text
    download_resp = await client.get(
        f"/project-manager/api/solutions/{solution['solution_id']}/documents/{document_id}/download"
    )
    assert download_resp.status_code == 404, download_resp.text

    with db_sessionmaker() as session:
        stored = session.query(SolutionDocument).filter(SolutionDocument.document_id == document_id).one()
        assert stored.deleted_at is None
