import pytest

from backend.app.models import User


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [False, True])
async def test_user_import_rejects_rows_with_more_values_than_headers(client, db_sessionmaker, dry_run):
    response = await client.post(
        f"/project-manager/api/users/import?dry_run={str(dry_run).lower()}",
        content=b"soeid,display_name\nbad,Bad,unexpected\ngood,Good\n",
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["count"] == 1
    assert response.json()["errors"] == ["Row 2: too many columns for the CSV header"]
    with db_sessionmaker() as session:
        assert session.query(User).filter(User.soeid == "bad").count() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("column", ["capacity_fte_month", "capacity_hours"])
@pytest.mark.parametrize("invalid_capacity", ["nan", "inf", "-inf", "1e309"])
@pytest.mark.parametrize("dry_run", [False, True])
async def test_user_import_rejects_nonfinite_capacity_and_keeps_valid_rows(
    client, db_sessionmaker, column, invalid_capacity, dry_run
):
    csv_text = f"soeid,display_name,{column}\nbad,Bad,{invalid_capacity}\ngood,Good,1\n"
    response = await client.post(
        f"/project-manager/api/users/import?dry_run={str(dry_run).lower()}",
        content=csv_text.encode(), headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["count"] == 1
    assert payload["created"] == 1
    assert payload["total_rows"] == 2
    assert payload["errors"] == [f"Row 2: invalid {column} '{invalid_capacity}'"]
    with db_sessionmaker() as session:
        assert session.query(User).filter(User.soeid == "bad").count() == 0
        assert session.query(User).filter(User.soeid == "good").count() == (0 if dry_run else 1)
