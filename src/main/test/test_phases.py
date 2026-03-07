import pytest

from backend.app.models import Phase


def seed_phases(SessionLocal):
    with SessionLocal() as session:
        session.add_all(
            [
                Phase(
                    phase_id="backlog",
                    phase_group="Backlog",
                    phase_name="Backlog",
                    sequence=1,
                ),
                Phase(
                    phase_id="requirements",
                    phase_group="Planning",
                    phase_name="Requirements",
                    sequence=2,
                ),
                Phase(
                    phase_id="uat",
                    phase_group="Deployment",
                    phase_name="UAT Deployment",
                    sequence=3,
                ),
            ]
        )
        session.commit()


async def create_project_and_solution(client):
    project = (
        await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Data Platform",
            "description": "Modernize data stack",
            "sponsor": "CFO Office",
        },
        )
    ).json()
    solution = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Access Controls", "version": "0.1.0", "owner": "Solution Owner"},
        )
    ).json()
    return project, solution


@pytest.mark.anyio
async def test_list_phases(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    resp = await client.get("/project-manager/api/phases")
    assert resp.status_code == 200
    data = resp.json()
    assert [p["phase_id"] for p in data] == ["backlog", "requirements", "uat"]


@pytest.mark.anyio
async def test_set_and_get_solution_phases(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_and_solution(client)
    solution_id = solution["solution_id"]

    # Set the solution's current phase so we can verify it gets cleared if disabled.
    resp = await client.patch(f"/project-manager/api/solutions/{solution_id}", json={"current_phase": "requirements"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["current_phase"] == "requirements"

    set_resp = await client.post(
        f"/project-manager/api/solutions/{solution_id}/phases",
        json={
            "phases": [
                {"phase_id": "backlog", "is_enabled": True},
                {"phase_id": "requirements", "is_enabled": True, "sequence_override": 5},
                {"phase_id": "uat", "is_enabled": False},
            ]
        },
    )
    assert set_resp.status_code == 200, set_resp.text
    items = set_resp.json()
    assert len(items) == 3
    assert items[0]["phase_id"] == "backlog"
    assert items[0]["is_enabled"] is True

    list_resp = await client.get(f"/project-manager/api/solutions/{solution_id}/phases")
    assert list_resp.status_code == 200
    listed = list_resp.json()
    assert len(listed) == 3
    assert [p["phase_id"] for p in listed] == ["backlog", "uat", "requirements"]
    requirements = next(p for p in listed if p["phase_id"] == "requirements")
    assert requirements["sequence_override"] == 5

    # Disabling the current phase clears it.
    disable_resp = await client.post(
        f"/project-manager/api/solutions/{solution_id}/phases",
        json={"phases": [{"phase_id": "requirements", "is_enabled": False}]},
    )
    assert disable_resp.status_code == 200
    updated_solution = (await client.get(f"/project-manager/api/solutions/{solution_id}")).json()
    assert updated_solution["current_phase"] is None
