from __future__ import annotations

import pytest

from test_agent_api import _auth_headers, _seed_work_graph, agent_client, override_db_only  # noqa: F401


@pytest.mark.anyio
async def test_interactive_updates_reject_null_required_values_and_allow_nullable_clears(client):
    project_response = await client.post(
        "/project-manager/api/projects/", json={"project_name": "Null validation project", "description": "Before"}
    )
    assert project_response.status_code == 201
    project = project_response.json()
    solution_response = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Null validation solution", "description": "Before"},
    )
    assert solution_response.status_code == 201
    solution = solution_response.json()
    for path, fields in [
        (f"/project-manager/api/projects/{project['project_id']}", ("status", "priority", "sponsor")),
        (f"/project-manager/api/solutions/{solution['solution_id']}", ("status", "owner", "assignee")),
    ]:
        for field in fields:
            response = await client.patch(path, json={field: None})
            assert response.status_code == 422, (field, response.text)
        clear = await client.patch(path, json={"description": None})
        assert clear.status_code == 200, clear.text
        assert clear.json()["description"] is None


@pytest.mark.anyio
async def test_agent_patch_validation_rejects_null_required_values(agent_client, db_sessionmaker):  # noqa: F811
    token, space_id, _, _, project_id, solution_id, _, project_time, solution_time, _ = _seed_work_graph(db_sessionmaker)
    operations = []
    for entity, entity_id, updated_at, fields in [
        ("project", project_id, project_time, ("status", "priority", "sponsor")),
        ("solution", solution_id, solution_time, ("status", "owner", "assignee")),
    ]:
        for field in fields:
            operations.append({
                "client_operation_id": f"{entity}-{field}", "op": "update", "entity": entity,
                "id": entity_id, "if_updated_at": updated_at, "fields": {field: None},
            })
    response = await agent_client.post(
        "/project-manager/api/agent/patches/validate", headers=_auth_headers(token, space_id),
        json={"dry_run": True, "operations": operations},
    )
    assert response.status_code == 200, response.text
    assert response.json()["valid"] is False
    assert all(row["code"] == "VALIDATION_ERROR" for row in response.json()["results"])
