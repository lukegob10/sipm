from __future__ import annotations

import pytest

from test_agent_api import _auth_headers, _seed_agent_token, _seed_cookie_user, agent_client, override_db_only  # noqa: F401
from backend.app.models import Program, Project, Solution, Task


def _hierarchy():
    return {
        "reason": "Build a reviewed hierarchy", "idempotency_key": "partial-hierarchy",
        "operations": [
            {"client_operation_id": "program", "op": "create", "entity": "program", "ref": "p",
             "fields": {"program_name": "Partial Program"}},
            {"client_operation_id": "project", "op": "create", "entity": "project", "ref": "j", "program_ref": "p",
             "fields": {"project_name": "Partial Project"}},
            {"client_operation_id": "solution", "op": "create", "entity": "solution", "ref": "s", "project_ref": "j",
             "fields": {"solution_name": "Partial Solution"}},
            {"client_operation_id": "task", "op": "create", "entity": "task", "solution_ref": "s",
             "fields": {"task_name": "Partial Task"}},
        ],
    }


async def _submit_and_login(client, db_sessionmaker):
    token, space_id = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space_id, soeid="partial-review", user_id="reviewer")
    submitted = await client.post("/project-manager/api/agent/change-requests", headers=_auth_headers(token, space_id), json=_hierarchy())
    assert submitted.status_code == 201, submitted.text
    login = await client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200, login.text
    return submitted.json(), space_id


async def _approve(client, request_id, space_id, selected):
    reviewed = await client.get(
        f"/project-manager/api/agent/change-requests/{request_id}", headers={"X-Space-Id": space_id},
    )
    assert reviewed.status_code == 200, reviewed.text
    return await client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/approve-selected-operations",
        headers={"X-Space-Id": space_id}, json={"client_operation_ids": selected,
            "if_request_fingerprint": reviewed.json()["content_fingerprint"]},
    )


@pytest.mark.anyio
async def test_partial_approval_resolves_each_created_parent_for_the_remainder(agent_client, db_sessionmaker):  # noqa: F811
    initial, space_id = await _submit_and_login(agent_client, db_sessionmaker)
    request_id = initial["change_request_id"]
    for parent, child, ref_name, id_location in [
        ("program", "project", "program_ref", "program_id"),
        ("project", "solution", "project_ref", "project_id"),
        ("solution", "task", "solution_ref", "solution_id"),
    ]:
        response = await _approve(agent_client, request_id, space_id, [parent])
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "pending" and body["validation"]["valid"] is True
        assert [item["client_operation_id"] for item in body["diff"]] == [item["client_operation_id"] for item in body["operations"]]
        operation = next(item for item in body["operations"] if item["client_operation_id"] == child)
        assert operation[ref_name] is None
        entity_id = operation["fields"][id_location] if id_location == "program_id" else operation[id_location]
        assert entity_id
        with db_sessionmaker() as session:
            model = {"program": Program, "project": Project, "solution": Solution}[parent]
            assert session.get(model, entity_id) is not None

    response = await _approve(agent_client, request_id, space_id, ["task"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"
    with db_sessionmaker() as session:
        program = session.query(Program).filter_by(program_name="Partial Program").one()
        project = session.query(Project).filter_by(project_name="Partial Project").one()
        solution = session.query(Solution).filter_by(solution_name="Partial Solution").one()
        task = session.query(Task).filter_by(task_name="Partial Task").one()
        assert project.program_id == program.program_id
        assert solution.project_id == project.project_id
        assert task.solution_id == solution.solution_id


@pytest.mark.anyio
async def test_child_without_selected_parent_is_rejected_without_mutating_request(agent_client, db_sessionmaker):  # noqa: F811
    initial, space_id = await _submit_and_login(agent_client, db_sessionmaker)
    request_id = initial["change_request_id"]
    response = await _approve(agent_client, request_id, space_id, ["solution"])
    assert response.status_code == 400, response.text
    refreshed = await agent_client.get(f"/project-manager/api/agent/change-requests/{request_id}", headers={"X-Space-Id": space_id})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["status"] == "pending"
    assert body["operations"] == initial["operations"]
    assert body["validation"] == initial["validation"]
    assert body["diff"] == initial["diff"]
    assert body["reviewed_at"] is None
    with db_sessionmaker() as session:
        assert session.query(Program).filter_by(program_name="Partial Program").count() == 0
        assert session.query(Solution).filter_by(solution_name="Partial Solution").count() == 0


@pytest.mark.anyio
async def test_approving_multiple_linked_parents_resolves_remainder(agent_client, db_sessionmaker):  # noqa: F811
    initial, space_id = await _submit_and_login(agent_client, db_sessionmaker)
    response = await _approve(agent_client, initial["change_request_id"], space_id, ["program", "project"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending" and body["validation"]["valid"] is True
    solution = body["operations"][0]
    assert solution["client_operation_id"] == "solution" and solution["project_ref"] is None
    assert solution["project_id"]
    response = await _approve(agent_client, initial["change_request_id"], space_id, ["solution", "task"])
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "approved"


@pytest.mark.anyio
async def test_missing_applied_parent_id_rolls_back_partial_approval(agent_client, db_sessionmaker, monkeypatch):  # noqa: F811
    from backend.app.services import agent_change_requests as requests

    initial, space_id = await _submit_and_login(agent_client, db_sessionmaker)
    request_id = initial["change_request_id"]
    original_apply = requests._apply_patch_plan_locked

    def missing_result_id(*args, **kwargs):
        result = original_apply(*args, **kwargs)
        assert result.applied
        result.results[0].entity_id = None
        return result

    monkeypatch.setattr(requests, "_apply_patch_plan_locked", missing_result_id)
    with pytest.raises(RuntimeError, match="missing its entity ID"):
        await _approve(agent_client, request_id, space_id, ["program"])
    with db_sessionmaker() as session:
        assert session.query(Program).filter_by(program_name="Partial Program").count() == 0
    refreshed = await agent_client.get(f"/project-manager/api/agent/change-requests/{request_id}", headers={"X-Space-Id": space_id})
    assert refreshed.status_code == 200, refreshed.text
    body = refreshed.json()
    assert body["status"] == "pending"
    assert body["operations"] == initial["operations"]
    assert body["reviewed_at"] is None
