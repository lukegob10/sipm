import pytest

from backend.app.utils import parse_datetime


@pytest.mark.parametrize("value", ["0001-01-01T00:00:00+14:00", "9999-12-31T23:59:59-12:00"])
def test_parse_datetime_reports_timezone_overflow_as_invalid(value):
    with pytest.raises(ValueError, match="invalid datetime"):
        parse_datetime(value)


@pytest.mark.anyio
@pytest.mark.parametrize("kind", ["solutions", "tasks"])
@pytest.mark.parametrize("dry_run", [False, True])
async def test_csv_invalid_datetime_is_reported_and_later_rows_continue(client, kind, dry_run):
    if kind == "solutions":
        content = ("project_name,solution_name,status,completed_at\n"
                   "Project,Invalid,complete,0001-01-01T00:00:00+14:00\n"
                   "Project,Valid,complete,2026-01-01T12:00:00Z\n")
    else:
        content = ("project_name,solution_name,task_name,status,completed_at\n"
                   "Project,Solution,Invalid,complete,9999-12-31T23:59:59-12:00\n"
                   "Project,Solution,Valid,complete,2026-01-01T12:00:00Z\n")
    response = await client.post(f"/project-manager/api/{kind}/import?dry_run={str(dry_run).lower()}",
                                 content=content, headers={"Content-Type": "text/csv"})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 1
    assert len(result["errors"]) == 1
    assert "invalid datetime" in result["errors"][0]
