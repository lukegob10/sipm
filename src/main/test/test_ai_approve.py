import json

import pytest

from backend.app.routes import ai as ai_route
from backend.app.routes import genai as genai_route


@pytest.mark.anyio
async def test_ai_approve_project_create_defaults_sponsor_user_soeid(client):
    # When the draft resolves sponsor to the current user, AI approve should persist sponsor_user_soeid.
    output = json.dumps({"fields": {"project_name": "AI Approved Project", "sponsor": "Test User"}})
    resp = await client.post(
        "/api/ai/approve",
        json={
            "request_type": "project_create",
            "entity_type": "project",
            "output": output,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["reply"] == "Saved."
    assert data["entity_type"] == "project"
    assert data["entity_id"]

    project_resp = await client.get(f"/api/projects/{data['entity_id']}")
    assert project_resp.status_code == 200, project_resp.text
    project = project_resp.json()
    assert project["project_name"] == "AI Approved Project"
    assert project["sponsor"] == "Test User"
    assert project["sponsor_user_soeid"] == "tu12345"


@pytest.mark.anyio
async def test_ai_approve_project_create_invalid_priority_falls_back_to_default(client):
    output = json.dumps({"fields": {"project_name": "AI Invalid Priority Project", "priority": "high"}})
    resp = await client.post(
        "/api/ai/approve",
        json={
            "request_type": "project_create",
            "entity_type": "project",
            "output": output,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["entity_type"] == "project"
    assert data["entity_id"]

    project_resp = await client.get(f"/api/projects/{data['entity_id']}")
    assert project_resp.status_code == 200, project_resp.text
    project = project_resp.json()
    assert project["priority"] == 3


@pytest.mark.anyio
async def test_ai_approve_autofill_applies_bulk_updates_across_entity_types(client):
    project_resp = await client.post(
        "/api/projects/",
        json={"project_name": "Bulk Autofill Project", "status": "active", "sponsor": "Test User"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    solution_resp = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Bulk Solution", "version": "0.1.0", "owner": "Legacy Owner"},
    )
    assert solution_resp.status_code == 201, solution_resp.text
    solution = solution_resp.json()

    subcomponent_resp = await client.post(
        f"/api/solutions/{solution['solution_id']}/subcomponents",
        json={"subcomponent_name": "Bulk Task", "blocked": False, "priority": 3},
    )
    assert subcomponent_resp.status_code == 201, subcomponent_resp.text
    subcomponent = subcomponent_resp.json()

    output = json.dumps(
        {
            "updates": [
                {
                    "entity_type": "project",
                    "entity_id": project["project_id"],
                    "fields": {"status": "on_hold"},
                },
                {
                    "entity_type": "solution",
                    "entity_id": solution["solution_id"],
                    "fields": {"owner": "Gustavo Rubim"},
                },
                {
                    "entity_type": "subcomponent",
                    "entity_id": subcomponent["subcomponent_id"],
                    "fields": {"blocked": True},
                },
            ]
        }
    )

    approve_resp = await client.post(
        "/api/ai/approve",
        json={
            "request_type": "autofill",
            "entity_type": "project",
            "entity_id": project["project_id"],
            "output": output,
        },
    )
    assert approve_resp.status_code == 200, approve_resp.text
    approved = approve_resp.json()
    assert approved["reply"] == "Saved. Updated 3 items."

    project_check = await client.get(f"/api/projects/{project['project_id']}")
    assert project_check.status_code == 200, project_check.text
    assert project_check.json()["status"] == "on_hold"

    solution_check = await client.get(f"/api/solutions/{solution['solution_id']}")
    assert solution_check.status_code == 200, solution_check.text
    assert solution_check.json()["owner"] == "Gustavo Rubim"

    subcomponent_check = await client.get(f"/api/subcomponents/{subcomponent['subcomponent_id']}")
    assert subcomponent_check.status_code == 200, subcomponent_check.text
    assert subcomponent_check.json()["blocked"] is True


@pytest.mark.anyio
async def test_ai_approve_infers_autofill_when_request_type_missing_and_updates_are_solution_shaped(client):
    project_resp = await client.post(
        "/api/projects/",
        json={"project_name": "Infer Missing Request Type Project", "status": "active", "sponsor": "Test User"},
    )
    assert project_resp.status_code == 201, project_resp.text
    project = project_resp.json()

    s1_resp = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Infer One", "version": "0.1.0", "owner": "Legacy Owner"},
    )
    assert s1_resp.status_code == 201, s1_resp.text
    s1 = s1_resp.json()

    s2_resp = await client.post(
        f"/api/projects/{project['project_id']}/solutions",
        json={"solution_name": "Infer Two", "version": "0.1.0", "owner": "Legacy Owner"},
    )
    assert s2_resp.status_code == 201, s2_resp.text
    s2 = s2_resp.json()

    output = json.dumps(
        {
            "updates": [
                {
                    "solution_id": s1["solution_id"],
                    "solution_name": s1["solution_name"],
                    "owner": "Gustavo Rubim",
                },
                {
                    "solution_id": s2["solution_id"],
                    "solution_name": s2["solution_name"],
                    "owner": "Gustavo Rubim",
                },
            ]
        }
    )

    approve_resp = await client.post(
        "/api/ai/approve",
        json={
            "request_type": "",
            "entity_type": "project",
            "entity_id": project["project_id"],
            "output": output,
        },
    )
    assert approve_resp.status_code == 200, approve_resp.text
    approved = approve_resp.json()
    assert approved["request_type"] == "autofill"
    assert approved["reply"] == "Saved. Updated 2 items."

    s1_check = await client.get(f"/api/solutions/{s1['solution_id']}")
    assert s1_check.status_code == 200, s1_check.text
    assert s1_check.json()["owner"] == "Gustavo Rubim"

    s2_check = await client.get(f"/api/solutions/{s2['solution_id']}")
    assert s2_check.status_code == 200, s2_check.text
    assert s2_check.json()["owner"] == "Gustavo Rubim"


def test_compact_ai_request_output_is_bounded_for_ai_routes():
    long_text = "x" * 1000
    compact_ai = ai_route._compact_ai_request_output(long_text)
    compact_genai = genai_route._compact_ai_request_output(long_text)
    assert compact_ai is not None and len(compact_ai) <= 255
    assert compact_genai is not None and len(compact_genai) <= 255
    assert "truncated 1000 chars" in compact_ai
    assert "truncated 1000 chars" in compact_genai


def test_ai_request_audit_summary_is_concise_and_includes_tools():
    payload = json.dumps(
        {
            "updates": [
                {
                    "entity_type": "solution",
                    "entity_id": "abc",
                    "fields": {"owner": "Gustavo Rubim"},
                },
                {
                    "entity_type": "solution",
                    "entity_id": "def",
                    "fields": {"owner": "Gustavo Rubim"},
                },
            ]
        }
    )
    summary = ai_route._build_ai_request_audit_summary(
        "autofill",
        "solution",
        "abc",
        payload,
        audit_tools=["search_entities", "read_context", "draft_update"],
    )
    assert len(summary) <= 255
    assert "autofill applied 2 update(s)" in summary
    assert "fields: owner" in summary
    assert "tools: search_entities, read_context, draft_update" in summary
