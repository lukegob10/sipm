import pytest
from sqlalchemy import event

from backend.app.models import SolutionDocument


def _capture_selects(engine):
    statements = []

    def record_select(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record_select)
    return statements, record_select


def _stop_capture(engine, listener):
    event.remove(engine, "before_cursor_execute", listener)


async def _create_solution(client):
    project_response = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": "Document Read Review Project"},
    )
    assert project_response.status_code == 201, project_response.text
    solution_response = await client.post(
        f"/project-manager/api/projects/{project_response.json()['project_id']}/solutions",
        json={"solution_name": "Document Read Review Solution"},
    )
    assert solution_response.status_code == 201, solution_response.text
    return solution_response.json()["solution_id"]


async def _upload_document(client, solution_id, filename, content):
    response = await client.post(
        f"/project-manager/api/solutions/{solution_id}/documents",
        files={"file": (filename, content, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.anyio
async def test_document_metadata_reads_defer_content_and_download_keeps_exact_bytes(
    client, db_sessionmaker
):
    solution_id = await _create_solution(client)
    first_content = b"first large document block" * 40_000
    second_content = b"second large document block" * 30_000
    first = await _upload_document(client, solution_id, "first.bin", first_content)
    second = await _upload_document(client, solution_id, "second.bin", second_content)

    engine = db_sessionmaker.kw["bind"]
    list_statements, list_listener = _capture_selects(engine)
    try:
        listed = await client.get(
            f"/project-manager/api/solutions/{solution_id}/documents"
        )
    finally:
        _stop_capture(engine, list_listener)

    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert {row["document_id"] for row in rows} == {
        first["document_id"],
        second["document_id"],
    }
    assert all(row["size_bytes"] > 0 and "content" not in row for row in rows)
    document_selects = [
        statement.lower()
        for statement in list_statements
        if SolutionDocument.__tablename__.lower() in statement.lower()
    ]
    assert len(list_statements) == 2  # solution existence plus one document metadata query
    assert len(document_selects) == 1
    assert f".{SolutionDocument.content.key} as " not in document_selects[0]

    downloaded = await client.get(
        f"/project-manager/api/solutions/{solution_id}/documents/{first['document_id']}/download"
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == first_content

    delete_statements, delete_listener = _capture_selects(engine)
    try:
        deleted = await client.delete(
            f"/project-manager/api/solutions/{solution_id}/documents/{second['document_id']}"
        )
    finally:
        _stop_capture(engine, delete_listener)

    assert deleted.status_code == 204, deleted.text
    delete_document_selects = [
        statement.lower()
        for statement in delete_statements
        if SolutionDocument.__tablename__.lower() in statement.lower()
    ]
    assert len(delete_document_selects) == 1
    assert f".{SolutionDocument.content.key} as " not in delete_document_selects[0]
