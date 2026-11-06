import pytest


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", "1e308"])
async def test_team_rejects_invalid_fte_on_create_and_update(client, value):
    created = await client.post("/project-manager/api/teams", json={"name": "Valid team"})
    assert created.status_code == 201
    team_id = created.json()["team_id"]

    create = await client.post(
        "/project-manager/api/teams",
        json={"name": "Invalid team", "default_capacity_fte_month": value},
    )
    assert create.status_code == 422
    update = await client.patch(
        f"/project-manager/api/teams/{team_id}",
        json={"default_capacity_fte_month": value},
    )
    assert update.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("field", "value"),
    [("capacity_fte_month", value) for value in ("NaN", "Infinity", "-Infinity", "1e308")]
    + [("percent_capacity", value) for value in ("NaN", "Infinity", "-Infinity")],
)
async def test_team_member_rejects_invalid_capacity_on_create_and_update(client, field, value):
    team = await client.post("/project-manager/api/teams", json={"name": "Capacity team"})
    assert team.status_code == 201
    team_id = team.json()["team_id"]
    member = await client.post(
        f"/project-manager/api/teams/{team_id}/members", json={"member_name": "Valid member"}
    )
    assert member.status_code == 201
    member_id = member.json()["team_member_id"]

    create = await client.post(
        f"/project-manager/api/teams/{team_id}/members",
        json={"member_name": "Invalid member", field: value},
    )
    assert create.status_code == 422
    update = await client.patch(
        f"/project-manager/api/teams/{team_id}/members/{member_id}", json={field: value}
    )
    assert update.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_name", ["", "   ", "x" * 256])
async def test_team_and_member_names_respect_required_database_columns(client, invalid_name):
    teams = "/project-manager/api/teams"
    team = await client.post(teams, json={"name": "Valid team"})
    assert team.status_code == 201
    team_id = team.json()["team_id"]
    member = await client.post(f"{teams}/{team_id}/members", json={"member_name": "Valid member"})
    assert member.status_code == 201
    member_id = member.json()["team_member_id"]

    requests = [
        ("post", teams, {"name": invalid_name}),
        ("patch", f"{teams}/{team_id}", {"name": invalid_name}),
        ("post", f"{teams}/{team_id}/members", {"member_name": invalid_name}),
        ("patch", f"{teams}/{team_id}/members/{member_id}", {"member_name": invalid_name}),
    ]
    for method, path, payload in requests:
        response = await getattr(client, method)(path, json=payload)
        assert response.status_code == 422, response.text

    detail = await client.get(f"{teams}/{team_id}")
    assert detail.json()["name"] == "Valid team"
    assert detail.json()["members"][0]["member_name"] == "Valid member"


@pytest.mark.anyio
async def test_team_and_member_names_allow_database_column_limit(client):
    name = "x" * 255
    team = await client.post("/project-manager/api/teams", json={"name": name})
    assert team.status_code == 201, team.text
    member = await client.post(
        f"/project-manager/api/teams/{team.json()['team_id']}/members", json={"member_name": name}
    )
    assert member.status_code == 201, member.text
    assert member.json()["member_name"] == name
