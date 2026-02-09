import json

import pytest


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
