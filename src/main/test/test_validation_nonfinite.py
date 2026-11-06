import pytest


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", '{"nested": [NaN]}'])
async def test_nonfinite_number_in_invalid_request_returns_validation_error(client, value):
    response = await client.post(
        "/project-manager/api/projects/",
        content=f'{{"project_name": "Project", "priority": {value}}}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "priority"]


@pytest.mark.anyio
@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
async def test_solution_confidence_rejects_nonfinite_values_on_create_and_update(client, value):
    project = await client.post("/project-manager/api/projects/", json={"project_name": "Project"})
    assert project.status_code == 201
    project_id = project.json()["project_id"]
    solution = await client.post(
        f"/project-manager/api/projects/{project_id}/solutions",
        json={"solution_name": "Valid", "rag_confidence": 0.5},
    )
    assert solution.status_code == 201
    create = await client.post(
        f"/project-manager/api/projects/{project_id}/solutions",
        json={"solution_name": "Invalid", "rag_confidence": value},
    )
    assert create.status_code == 422
    update = await client.patch(
        f"/project-manager/api/solutions/{solution.json()['solution_id']}", json={"rag_confidence": value}
    )
    assert update.status_code == 422
    detail = await client.get(f"/project-manager/api/solutions/{solution.json()['solution_id']}")
    assert detail.json()["rag_confidence"] == 0.5
