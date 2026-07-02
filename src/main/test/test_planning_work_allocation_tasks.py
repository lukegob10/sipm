import pytest

from backend.app import deps as deps_module
from backend.app.models import Space
from backend.app.services.spaces import SpaceContext
from backend.main import app as fastapi_app


@pytest.fixture(autouse=True)
def planning_space(db_sessionmaker):
    space_id = "space-planning-work-allocation"
    with db_sessionmaker() as session:
        if not session.query(Space).filter(Space.space_id == space_id).first():
            session.add(
                Space(
                    space_id=space_id,
                    name="Planning Work Allocation Space",
                    slug="planning-work-allocation-space",
                    is_active=True,
                )
            )
            session.commit()
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
        space_id=space_id,
        space_name="Planning Work Allocation Space",
        is_global_admin=False,
        space_role="space_admin",
    )
    try:
        yield
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


async def create_regular_task(client, name: str, capacity_hours: int = 80):
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

    task_resp = await client.post(
        f"/project-manager/api/solutions/{solution_id}/tasks",
        json={
            "task_name": name,
            "estimate_hours": capacity_hours,
            "capacity_hours": capacity_hours,
        },
    )
    assert task_resp.status_code == 201, task_resp.text
    payload = task_resp.json()
    payload["project_id"] = project_id
    payload["solution_id"] = solution_id
    return payload


@pytest.mark.anyio
async def test_planning_task_list_includes_regular_tasks(client):
    task = await create_regular_task(client, "Planning Visible Task")

    response = await client.get("/project-manager/api/planning/work-allocation/tasks?month=2026-03")
    assert response.status_code == 200, response.text

    rows = response.json()
    task = next((row for row in rows if row["id"] == task["task_id"]), None)
    assert task is not None
    assert task["title"] == "Planning Visible Task"
    assert task["fte_months"] == pytest.approx(0.5, abs=1e-6)
    assert task["status"] == "backlog"


@pytest.mark.anyio
async def test_planning_allocation_can_target_regular_tasks(client):
    task = await create_regular_task(client, "Planning Assigned Task")

    team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Platform Team"},
    )
    assert team_resp.status_code == 201, team_resp.text
    team_id = team_resp.json()["id"]

    allocation_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "task_id": task["task_id"],
            "assignee_type": "team",
            "assignee_id": team_id,
            "month": "2026-03",
            "fte_months_allocated": 0.5,
        },
    )
    assert allocation_resp.status_code == 201, allocation_resp.text
    allocation = allocation_resp.json()
    assert allocation["task_id"] == task["task_id"]
    assert allocation["assignee_type"] == "team"
    assert allocation["assignee_id"] == team_id

    duplicate_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "task_id": task["task_id"],
            "assignee_type": "team",
            "assignee_id": team_id,
            "month": "2026-03",
            "fte_months_allocated": 0.5,
        },
    )
    assert duplicate_resp.status_code == 201, duplicate_resp.text
    duplicate = duplicate_resp.json()
    assert duplicate["id"] == allocation["id"]

    tasks_resp = await client.get("/project-manager/api/planning/work-allocation/tasks?month=2026-03")
    assert tasks_resp.status_code == 200, tasks_resp.text
    rows = tasks_resp.json()
    task = next((row for row in rows if row["id"] == task["task_id"]), None)
    assert task is not None
    assert task["status"] == "assigned"

    allocations_resp = await client.get("/project-manager/api/planning/work-allocation/allocations?month=2026-03")
    assert allocations_resp.status_code == 200, allocations_resp.text
    allocations = allocations_resp.json()
    assert any(row["id"] == allocation["id"] for row in allocations)


@pytest.mark.anyio
async def test_planning_board_snapshot_returns_projects_solutions_teams_people_and_allocations(client):
    created_task = await create_regular_task(client, "Planning Snapshot Task", capacity_hours=120)

    team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Snapshot Team"},
    )
    assert team_resp.status_code == 201, team_resp.text
    team = team_resp.json()

    allocation_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "work_item_type": "project",
            "work_item_id": created_task["project_id"],
            "assignee_type": "team",
            "assignee_id": team["id"],
            "month": "2026-03",
        },
    )
    assert allocation_resp.status_code == 201, allocation_resp.text
    allocation = allocation_resp.json()

    response = await client.get("/project-manager/api/planning/work-allocation/board?month=2026-03")
    assert response.status_code == 200, response.text

    payload = response.json()
    assert set(payload) == {"projects", "solutions", "teams", "people", "allocations"}
    project = next((row for row in payload["projects"] if row["id"] == created_task["project_id"]), None)
    assert project is not None
    assert project["title"] == "Planning Snapshot Task Project"
    assert project["fte_months"] == pytest.approx(0.75, abs=1e-6)
    assert project["residual_fte_months"] == pytest.approx(0.75, abs=1e-6)
    assert project["solution_count"] == 1
    solution = next((row for row in payload["solutions"] if row["id"] == created_task["solution_id"]), None)
    assert solution is not None
    assert solution["title"] == "Planning Snapshot Task Solution"
    assert solution["fte_months"] == pytest.approx(0.75, abs=1e-6)
    assert solution["remaining_fte_months"] == pytest.approx(0.75, abs=1e-6)
    assert any(row["id"] == team["id"] and row["name"] == "Snapshot Team" for row in payload["teams"])
    assert any(
        row["id"] == allocation["id"]
        and row["work_item_type"] == "project"
        and row["work_item_id"] == created_task["project_id"]
        and row["task_id"] is None
        for row in payload["allocations"]
    )
    assert isinstance(payload["people"], list)


@pytest.mark.anyio
async def test_project_solution_planning_residual_rollup_and_parent_uniqueness(client):
    created_task = await create_regular_task(client, "Planning Residual Task", capacity_hours=160)

    owner_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Owner Team"},
    )
    assert owner_team_resp.status_code == 201, owner_team_resp.text
    owner_team = owner_team_resp.json()

    split_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Split Team"},
    )
    assert split_team_resp.status_code == 201, split_team_resp.text
    split_team = split_team_resp.json()

    second_split_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Second Split Team"},
    )
    assert second_split_team_resp.status_code == 201, second_split_team_resp.text
    second_split_team = second_split_team_resp.json()

    project_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "work_item_type": "project",
            "work_item_id": created_task["project_id"],
            "assignee_type": "team",
            "assignee_id": owner_team["id"],
            "month": "2026-03",
        },
    )
    assert project_resp.status_code == 201, project_resp.text
    project_allocation = project_resp.json()
    assert project_allocation["work_item_type"] == "project"
    assert project_allocation["work_item_id"] == created_task["project_id"]
    assert project_allocation["fte_months_allocated"] == pytest.approx(1.0, abs=1e-6)

    duplicate_project_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "work_item_type": "project",
            "work_item_id": created_task["project_id"],
            "assignee_type": "team",
            "assignee_id": split_team["id"],
            "month": "2026-03",
        },
    )
    assert duplicate_project_resp.status_code == 409, duplicate_project_resp.text
    assert duplicate_project_resp.json()["detail"] == "Project already has a parent allocation for this month"

    solution_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "work_item_type": "solution",
            "work_item_id": created_task["solution_id"],
            "assignee_type": "team",
            "assignee_id": split_team["id"],
            "month": "2026-03",
            "fte_months_allocated": 0.4,
        },
    )
    assert solution_resp.status_code == 201, solution_resp.text
    first_solution_allocation = solution_resp.json()

    over_solution_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "work_item_type": "solution",
            "work_item_id": created_task["solution_id"],
            "assignee_type": "team",
            "assignee_id": second_split_team["id"],
            "month": "2026-03",
            "fte_months_allocated": 0.8,
        },
    )
    assert over_solution_resp.status_code == 201, over_solution_resp.text

    board_resp = await client.get("/project-manager/api/planning/work-allocation/board?month=2026-03")
    assert board_resp.status_code == 200, board_resp.text
    board = board_resp.json()
    project = next(row for row in board["projects"] if row["id"] == created_task["project_id"])
    solution = next(row for row in board["solutions"] if row["id"] == created_task["solution_id"])
    parent_row = next(row for row in board["allocations"] if row["id"] == project_allocation["id"])
    assert project["fte_months"] == pytest.approx(1.0, abs=1e-6)
    assert project["allocated_solution_fte_months"] == pytest.approx(1.2, abs=1e-6)
    assert project["residual_fte_months"] == pytest.approx(0.0, abs=1e-6)
    assert solution["allocated_fte_months"] == pytest.approx(1.2, abs=1e-6)
    assert solution["remaining_fte_months"] == pytest.approx(0.0, abs=1e-6)
    assert parent_row["fte_months_allocated"] == pytest.approx(0.0, abs=1e-6)

    delete_resp = await client.delete(
        f"/project-manager/api/planning/work-allocation/allocations/{first_solution_allocation['id']}"
    )
    assert delete_resp.status_code == 204, delete_resp.text

    refreshed_resp = await client.get("/project-manager/api/planning/work-allocation/board?month=2026-03")
    assert refreshed_resp.status_code == 200, refreshed_resp.text
    refreshed = refreshed_resp.json()
    refreshed_project = next(row for row in refreshed["projects"] if row["id"] == created_task["project_id"])
    refreshed_parent = next(row for row in refreshed["allocations"] if row["id"] == project_allocation["id"])
    assert refreshed_project["allocated_solution_fte_months"] == pytest.approx(0.8, abs=1e-6)
    assert refreshed_project["residual_fte_months"] == pytest.approx(0.2, abs=1e-6)
    assert refreshed_parent["fte_months_allocated"] == pytest.approx(0.2, abs=1e-6)


@pytest.mark.anyio
async def test_project_allocation_can_move_between_teams_without_returning_to_backlog(client):
    created_task = await create_regular_task(client, "Planning Project Move Task", capacity_hours=80)

    first_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Project Move Source Team"},
    )
    assert first_team_resp.status_code == 201, first_team_resp.text
    first_team = first_team_resp.json()

    second_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Project Move Target Team"},
    )
    assert second_team_resp.status_code == 201, second_team_resp.text
    second_team = second_team_resp.json()

    allocation_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "work_item_type": "project",
            "work_item_id": created_task["project_id"],
            "assignee_type": "team",
            "assignee_id": first_team["id"],
            "month": "2026-03",
        },
    )
    assert allocation_resp.status_code == 201, allocation_resp.text
    allocation = allocation_resp.json()

    moved_resp = await client.patch(
        f"/project-manager/api/planning/work-allocation/allocations/{allocation['id']}",
        json={"assignee_type": "team", "assignee_id": second_team["id"]},
    )
    assert moved_resp.status_code == 200, moved_resp.text
    moved = moved_resp.json()
    assert moved["id"] == allocation["id"]
    assert moved["work_item_type"] == "project"
    assert moved["work_item_id"] == created_task["project_id"]
    assert moved["assignee_type"] == "team"
    assert moved["assignee_id"] == second_team["id"]

    board_resp = await client.get("/project-manager/api/planning/work-allocation/board?month=2026-03")
    assert board_resp.status_code == 200, board_resp.text
    board = board_resp.json()
    project_allocations = [
        row for row in board["allocations"]
        if row["work_item_type"] == "project" and row["work_item_id"] == created_task["project_id"]
    ]
    assert len(project_allocations) == 1
    assert project_allocations[0]["id"] == allocation["id"]
    assert project_allocations[0]["assignee_id"] == second_team["id"]


@pytest.mark.anyio
async def test_planning_allocation_can_move_between_teams_and_people(client):
    task = await create_regular_task(client, "Planning Reassigned Task")

    first_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Platform Team"},
    )
    assert first_team_resp.status_code == 201, first_team_resp.text
    first_team_id = first_team_resp.json()["id"]

    second_team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Operations Team"},
    )
    assert second_team_resp.status_code == 201, second_team_resp.text
    second_team_id = second_team_resp.json()["id"]

    person_resp = await client.post(
        "/project-manager/api/planning/work-allocation/people",
        json={"name": "Taylor Analyst", "team_id": second_team_id, "capacity_fte_months": 1.0},
    )
    assert person_resp.status_code == 201, person_resp.text
    person_id = person_resp.json()["id"]

    allocation_resp = await client.post(
        "/project-manager/api/planning/work-allocation/allocations",
        json={
            "task_id": task["task_id"],
            "assignee_type": "team",
            "assignee_id": first_team_id,
            "month": "2026-03",
            "fte_months_allocated": 0.5,
        },
    )
    assert allocation_resp.status_code == 201, allocation_resp.text
    created = allocation_resp.json()

    moved_team_resp = await client.patch(
        f"/project-manager/api/planning/work-allocation/allocations/{created['id']}",
        json={"assignee_type": "team", "assignee_id": second_team_id},
    )
    assert moved_team_resp.status_code == 200, moved_team_resp.text
    moved_team = moved_team_resp.json()
    assert moved_team["task_id"] == task["task_id"]
    assert moved_team["assignee_type"] == "team"
    assert moved_team["assignee_id"] == second_team_id

    moved_person_resp = await client.patch(
        f"/project-manager/api/planning/work-allocation/allocations/{moved_team['id']}",
        json={"assignee_type": "person", "assignee_id": person_id},
    )
    assert moved_person_resp.status_code == 200, moved_person_resp.text
    moved_person = moved_person_resp.json()
    assert moved_person["task_id"] == task["task_id"]
    assert moved_person["assignee_type"] == "person"
    assert moved_person["assignee_id"] == person_id

    allocations_resp = await client.get("/project-manager/api/planning/work-allocation/allocations?month=2026-03")
    assert allocations_resp.status_code == 200, allocations_resp.text
    task_allocations = [row for row in allocations_resp.json() if row["task_id"] == task["task_id"]]
    assert len(task_allocations) == 1
    assert task_allocations[0]["assignee_type"] == "person"
    assert task_allocations[0]["assignee_id"] == person_id


@pytest.mark.anyio
async def test_planning_task_create_preserves_explicit_zero_fte_as_minimum(client):
    response = await client.post(
        "/project-manager/api/planning/work-allocation/tasks",
        json={"title": "Planning Zero Effort Task", "fte_months": 0},
    )
    assert response.status_code == 201, response.text

    payload = response.json()
    assert payload["title"] == "Planning Zero Effort Task"
    assert payload["fte_months"] == pytest.approx(0.05, abs=1e-6)


@pytest.mark.anyio
async def test_planning_month_parameters_reject_impossible_months(client):
    for path in [
        "/project-manager/api/planning/work-allocation/board?month=2026-13",
        "/project-manager/api/planning/work-allocation/tasks?month=2026-00",
        "/project-manager/api/planning/work-allocation/allocations?month=2026-99",
        "/project-manager/api/planning/work-allocation/report.pdf?month=2026-13",
    ]:
        response = await client.get(path)
        assert response.status_code == 400, response.text
        assert response.json()["detail"] == "month must use YYYY-MM"


@pytest.mark.anyio
async def test_planning_team_and_person_updates_reject_blank_names(client):
    team_resp = await client.post(
        "/project-manager/api/planning/work-allocation/teams",
        json={"name": "Named Team"},
    )
    assert team_resp.status_code == 201, team_resp.text

    blank_team = await client.patch(
        f"/project-manager/api/planning/work-allocation/teams/{team_resp.json()['id']}",
        json={"name": "   "},
    )
    assert blank_team.status_code == 400, blank_team.text
    assert blank_team.json()["detail"] == "Team name is required"

    person_resp = await client.post(
        "/project-manager/api/planning/work-allocation/people",
        json={"name": "Named Person", "capacity_fte_months": 1.0},
    )
    assert person_resp.status_code == 201, person_resp.text

    blank_person = await client.patch(
        f"/project-manager/api/planning/work-allocation/people/{person_resp.json()['id']}",
        json={"name": "   "},
    )
    assert blank_person.status_code == 400, blank_person.text
    assert blank_person.json()["detail"] == "Person name is required"
