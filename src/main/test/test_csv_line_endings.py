import pytest

from backend.app.utils import read_csv


@pytest.mark.parametrize("ending", ["\n", "\r\n", "\r"])
def test_csv_reader_preserves_quoted_newlines_with_standard_record_endings(ending):
    content = f'project_name,description{ending}First,"line one\rline two"{ending}Second,plain{ending}'
    rows, errors = read_csv(content.encode())
    assert errors == []
    assert rows == [{"project_name": "First", "description": "line one\rline two"},
                    {"project_name": "Second", "description": "plain"}]


@pytest.mark.anyio
async def test_project_import_accepts_carriage_return_line_endings(client):
    response = await client.post("/project-manager/api/projects/import", content=b"project_name\rFirst\rSecond\r",
                                 headers={"Content-Type": "text/csv"})
    assert response.status_code == 200
    assert response.json()["created"] == 2
    assert response.json()["errors"] == []
