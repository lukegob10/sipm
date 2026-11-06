import pytest


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["description", "lead", "capacity_unit"])
async def test_team_metadata_column_limits(client, field):
    created = await client.post("/project-manager/api/teams", json={"name": "Valid Team", field: "x" * 255})
    assert created.status_code == 201, created.text
    assert created.json()[field] == "x" * 255
    invalid = await client.post("/project-manager/api/teams", json={"name": "Invalid Team", field: "x" * 256})
    assert invalid.status_code == 422
    changed = await client.patch(f"/project-manager/api/teams/{created.json()['team_id']}", json={field: "x" * 256})
    assert changed.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["role", "capacity_unit"])
async def test_member_metadata_column_limits(client, field):
    team = await client.post("/project-manager/api/teams", json={"name": "Team"})
    assert team.status_code == 201
    path = f"/project-manager/api/teams/{team.json()['team_id']}/members"
    member = await client.post(path, json={"member_name": "Valid", field: "x" * 255})
    assert member.status_code == 201, member.text
    assert member.json()[field] == "x" * 255
    invalid = await client.post(path, json={"member_name": "Invalid", field: "x" * 256})
    assert invalid.status_code == 422
    changed = await client.patch(f"{path}/{member.json()['team_member_id']}", json={field: "x" * 256})
    assert changed.status_code == 422
