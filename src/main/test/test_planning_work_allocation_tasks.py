import pytest


async def create_regular_subcomponent(client, name: str, capacity_hours: int = 80):
    project_resp = await client.post(
        "/project-manager/api/projects/",
        json={"project_name": f"{name} Project"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project_id = project_resp.json()["project_id"]

    solution_resp = await client.post(
        f"/project-manager/api/projects/{project_id}/solutions",
        json={"solution_name": f"{name} Solution"},
    )
    assert solution_resp.status_code == 201, solution_resp.text
    solution_id = solution_resp.json()["solution_id"]

    subcomponent_resp = await client.post(
        f"/project-manager/api/solutions/{solution_id}/subcomponents",
        json={
            "subcomponent_name": name,
            "estimate_hours": capacity_hours,
            "capacity_hours": capacity_hours,
        },
    )
    assert subcomponent_resp.status_code == 201, subcomponent_resp.text
    return subcomponent_resp.json()


@pytest.mark.anyio
async def test_planning_task_list_includes_regular_subcomponents(client):
    subcomponent = await create_regular_subcomponent(client, "Planning Visible Task")

    response = await client.get("/project-manager/api/planning/work-allocation/tasks?month=2026-03")
    assert response.status_code == 200, response.text

    rows = response.json()
    task = next((row for row in rows if row["id"] == subcomponent["subcomponent_id"]), None)
    assert task is not None
    assert task["title"] == "Planning Visible Task"
    assert task["fte_months"] == pytest.approx(0.5, abs=1e-6)
    assert task["status"] == "backlog"


@pytest.mark.anyio
async def test_planning_allocation_can_target_regular_subcomponents(client):
    subcomponent = await create_regular_subcomponent(client, "Planning Assigned Task")

    team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Platform Team"},
    )
    assert team_resp.status_code == 201, team_resp.text
    team_id = team_resp.json()["id"]

    allocation_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "task_id": subcomponent["subcomponent_id"],
            "assignee_type": "team",
            "assignee_id": team_id,
            "month": "2026-03",
            "fte_months_allocated": 0.5,
        },
    )
    assert allocation_resp.status_code == 201, allocation_resp.text
    allocation = allocation_resp.json()
    assert allocation["task_id"] == subcomponent["subcomponent_id"]
    assert allocation["assignee_type"] == "team"
    assert allocation["assignee_id"] == team_id

    tasks_resp = await client.get("/project-manager/api/planning/work-allocation/tasks?month=2026-03")
    assert tasks_resp.status_code == 200, tasks_resp.text
    rows = tasks_resp.json()
    task = next((row for row in rows if row["id"] == subcomponent["subcomponent_id"]), None)
    assert task is not None
    assert task["status"] == "assigned"

    allocations_resp = await client.get("/project-manager/api/planning/work-allocation/allocations?month=2026-03")
    assert allocations_resp.status_code == 200, allocations_resp.text
    allocations = allocations_resp.json()
    assert any(row["id"] == allocation["id"] for row in allocations)
