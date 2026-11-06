import pytest

from backend.app.models import Project
from backend.app.utils import read_csv


def test_duplicate_csv_headers_are_rejected_before_values_can_be_overwritten():
    rows, errors = read_csv(b"project_name,project_name\nFirst,Second\n")
    assert rows == []
    assert errors == ["Duplicate CSV header: project_name"]


@pytest.mark.anyio
async def test_project_import_with_duplicate_headers_saves_no_rows(client, db_sessionmaker):
    response = await client.post(
        "/project-manager/api/projects/import",
        content="project_name,project_name\nFirst,Second\n",
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200
    assert response.json()["created"] == 0
    assert response.json()["errors"] == ["Duplicate CSV header: project_name"]
    with db_sessionmaker() as session:
        assert session.query(Project).count() == 0
