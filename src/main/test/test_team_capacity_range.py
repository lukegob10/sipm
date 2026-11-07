import pytest


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [("default_capacity_fte_month", "1e100"), ("default_capacity_per_week", 10**100)])
async def test_team_rejects_capacity_outside_storage_range(client, field, value):
    existing = await client.post("/project-manager/api/teams", json={"name": "Existing"})
    assert existing.status_code == 201
    created = await client.post("/project-manager/api/teams", json={"name": "Too large", field: value})
    assert created.status_code == 422
    changed = await client.patch(f"/project-manager/api/teams/{existing.json()['team_id']}", json={field: value})
    assert changed.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [("capacity_fte_month", "1e100"), ("hours_capacity", 10**100),
                                          ("capacity_override", 10**100), ("points_capacity", 10**100)])
async def test_team_member_rejects_capacity_outside_storage_range(client, field, value):
    team = (await client.post("/project-manager/api/teams", json={"name": "Team"})).json()
    path = f"/project-manager/api/teams/{team['team_id']}/members"
    member = await client.post(path, json={"member_name": "Member"})
    assert member.status_code == 201
    created = await client.post(path, json={"member_name": "Invalid", field: value})
    assert created.status_code == 422
    changed = await client.patch(f"{path}/{member.json()['team_member_id']}", json={field: value})
    assert changed.status_code == 422


@pytest.mark.anyio
async def test_team_capacity_total_overflow_rolls_back_member(client):
    team = (await client.post("/project-manager/api/teams", json={"name": "Aggregate"})).json()
    path = f"/project-manager/api/teams/{team['team_id']}/members"
    first = await client.post(path, json={"member_name": "First", "hours_capacity": 1 << 62})
    assert first.status_code == 201, first.text
    second = await client.post(path, json={"member_name": "Second", "hours_capacity": 1 << 62})
    assert second.status_code == 422
    detail = await client.get(f"/project-manager/api/teams/{team['team_id']}")
    assert [member["member_name"] for member in detail.json()["members"]] == ["First"]
    assert detail.json()["default_capacity_per_week"] == 1 << 62
