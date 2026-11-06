import pytest


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [
    ("display_name", ""), ("display_name", "  "), ("display_name", "x" * 256), ("team_tag", "x" * 256),
])
async def test_user_update_rejects_invalid_database_strings(client, field, value):
    imported = await client.post(
        "/project-manager/api/users/import", content="soeid,display_name\nuser1,Original\n",
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["created"] == 1
    response = await client.patch("/project-manager/api/users/by-soeid/user1", json={field: value})
    assert response.status_code == 422
    users = await client.get("/project-manager/api/users")
    assert next(user for user in users.json() if user["soeid"] == "user1")["display_name"] == "Original"


@pytest.mark.anyio
async def test_user_update_accepts_database_column_limit(client):
    imported = await client.post(
        "/project-manager/api/users/import", content="soeid,display_name\nuser1,Original\n",
        headers={"Content-Type": "text/csv"},
    )
    assert imported.status_code == 200
    name = "x" * 255
    response = await client.patch(
        "/project-manager/api/users/by-soeid/user1", json={"display_name": name, "team_tag": name}
    )
    assert response.status_code == 200, response.text
    assert response.json()["display_name"] == name
    assert response.json()["team_tag"] == name


@pytest.mark.anyio
@pytest.mark.parametrize("dry_run", [False, True])
@pytest.mark.parametrize("field,value", [
    ("soeid", "x" * 256), ("display_name", "x" * 256), ("team_tag", "x" * 256), ("email", "x" * 250),
])
async def test_user_import_reports_overlong_values_and_continues(client, monkeypatch, field, value, dry_run):
    monkeypatch.setenv("DOMAIN_NAME", "citi.com")
    row = {"soeid": "bad", "display_name": "Bad", "team_tag": "Team"}
    row["soeid" if field == "email" else field] = value
    data = f"soeid,display_name,team_tag\n{row['soeid']},{row['display_name']},{row['team_tag']}\ngood,Good,Team\n"
    response = await client.post(
        f"/project-manager/api/users/import?dry_run={str(dry_run).lower()}", content=data,
        headers={"Content-Type": "text/csv"},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["created"] == 1
    assert result["errors"] == [f"Row 2: {field} must be 255 characters or fewer"]
