from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

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


def test_download_filename_header_excludes_ascii_control_characters():
    header = solution_documents_route._content_disposition("report\x00\x1f\x7f.txt")
    assert all(32 <= ord(char) <= 126 for char in header)
    assert "report%00%1F%7F.txt" in header


@pytest.mark.anyio
async def test_document_upload_returns_committed_metadata_without_post_commit_refresh(client, db_sessionmaker, monkeypatch):
    solution = await create_solution(client)
    published = []
    original_refresh = Session.refresh

    def fail_document_refresh(session, instance, *args, **kwargs):
        if isinstance(instance, SolutionDocument):
            raise RuntimeError("refresh failed")
        return original_refresh(session, instance, *args, **kwargs)

    monkeypatch.setattr(Session, "refresh", fail_document_refresh)
    monkeypatch.setattr(solution_documents_route, "_publish_solution_mutation", published.append)
    response = await upload_document(client, solution["solution_id"])
    assert response.status_code == 201, response.text
    assert response.json()["filename"] == "notes.txt"
    assert published == ["test-space"]
    with db_sessionmaker() as session:
        assert session.query(SolutionDocument).filter_by(solution_id=solution["solution_id"]).count() == 1


@pytest.mark.anyio
async def test_document_upload_rolls_back_if_metadata_cannot_be_built(client, db_sessionmaker, monkeypatch):
    solution = await create_solution(client)
    published = []
    monkeypatch.setattr(solution_documents_route, "_publish_solution_mutation", published.append)

    def fail_payload(_document):
        raise RuntimeError("metadata failed")

    monkeypatch.setattr(solution_documents_route, "_document_payload", fail_payload)
    with pytest.raises(RuntimeError, match="metadata failed"):
        await upload_document(client, solution["solution_id"])
    assert published == []
    with db_sessionmaker() as session:
        assert session.query(SolutionDocument).filter_by(solution_id=solution["solution_id"]).count() == 0


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
async def test_solution_documents_are_space_scoped(client, seed_space_memberships):
    seed_space_memberships("space-documents-a", "space-documents-b")
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
