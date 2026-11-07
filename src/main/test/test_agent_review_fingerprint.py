import pytest
from test_agent_api import agent_client, override_db_only, _seed_agent_token, _seed_cookie_user, _auth_headers  # noqa: F401


@pytest.mark.anyio
async def test_review_cannot_apply_changed_proposal(agent_client, db_sessionmaker):  # noqa: F811
    token, space = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space, soeid="reviewer", user_id="reviewer")
    path = "/project-manager/api/agent/change-requests"
    operation = {"client_operation_id": "create", "op": "create", "entity": "project", "fields": {"project_name": "Reviewed"}}
    submitted = await agent_client.post(path, headers=_auth_headers(token, space), json={
        "dry_run": False, "reason": "reviewed intent", "idempotency_key": "review-race", "operations": [operation],
    })
    assert submitted.status_code == 201, submitted.text
    request = submitted.json()
    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200, login.text
    observed = await agent_client.get(f"{path}/{request['change_request_id']}", headers={"X-Space-Id": space})
    assert observed.status_code == 200
    replacement = {**operation, "fields": {"project_name": "Not Reviewed"}}
    changed = await agent_client.put(f"{path}/{request['change_request_id']}", headers=_auth_headers(token, space), json={
        "if_request_updated_at": request["updated_at"], "if_request_fingerprint": request["content_fingerprint"], "reason": "changed intent", "operations": [replacement],
    })
    assert changed.status_code == 200, changed.text
    approved = await agent_client.post(f"{path}/{request['change_request_id']}/approve-selected-operations",
                                       headers={"X-Space-Id": space}, json={"client_operation_ids": ["create"],
                                                                          "if_request_fingerprint": observed.json()["content_fingerprint"]})
    assert approved.status_code == 409, approved.text
    assert approved.json()["code"] == "CHANGE_REQUEST_CHANGED"
    current = changed.json()
    assert current["content_fingerprint"] != observed.json()["content_fingerprint"]
    accepted = await agent_client.post(f"{path}/{request['change_request_id']}/approve-selected-operations",
        headers={"X-Space-Id": space}, json={"client_operation_ids": ["create"],
            "if_request_fingerprint": current["content_fingerprint"]})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "approved"


@pytest.mark.anyio
async def test_stale_fingerprint_rejected_even_when_timestamps_match(agent_client, db_sessionmaker):  # noqa: F811
    from datetime import datetime
    from backend.app.models import AgentChangeRequest

    token, space = _seed_agent_token(db_sessionmaker)
    path = "/project-manager/api/agent/change-requests"
    operation = {"client_operation_id": "create", "op": "create", "entity": "project", "fields": {"project_name": "First"}}
    response = await agent_client.post(path, headers=_auth_headers(token, space), json={
        "dry_run": False, "reason": "first", "idempotency_key": "same-time", "operations": [operation],
    })
    assert response.status_code == 201, response.text
    old = response.json()
    request_id = old["change_request_id"]
    replacement = {**operation, "fields": {"project_name": "Second"}}
    changed = await agent_client.put(f"{path}/{request_id}", headers=_auth_headers(token, space), json={
        "if_request_updated_at": old["updated_at"], "if_request_fingerprint": old["content_fingerprint"],
        "reason": "second", "operations": [replacement],
    })
    assert changed.status_code == 200, changed.text
    with db_sessionmaker() as session:
        row = session.get(AgentChangeRequest, request_id)
        row.updated_at = datetime.fromisoformat(old["updated_at"])
        session.commit()
    stale = await agent_client.put(f"{path}/{request_id}", headers=_auth_headers(token, space), json={
        "if_request_updated_at": old["updated_at"], "if_request_fingerprint": old["content_fingerprint"],
        "reason": "first", "operations": [operation],
    })
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "CHANGE_REQUEST_CHANGED"


@pytest.mark.anyio
async def test_changed_work_is_not_applied_from_old_review(agent_client, db_sessionmaker):  # noqa: F811
    from sqlalchemy import update
    from backend.app.models import Program, Project

    token, space = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space, soeid="reviewer", user_id="reviewer")
    with db_sessionmaker() as session:
        session.add_all([
            Program(program_id="program", space_id=space, program_name="Program"),
            Project(project_id="project", space_id=space, program_id="program", project_name="Project", description="original"),
        ])
        session.commit()
        original_updated_at = session.get(Project, "project").updated_at
    path = "/project-manager/api/agent/change-requests"
    submitted = await agent_client.post(path, headers=_auth_headers(token, space), json={
        "dry_run": False, "reason": "review description", "idempotency_key": "changed-work",
        "operations": [{"client_operation_id": "update", "op": "update", "entity": "project",
                        "id": "project", "if_updated_at": original_updated_at.isoformat(),
                        "fields": {"description": "proposed"}}],
    })
    assert submitted.status_code == 201, submitted.text
    proposal = submitted.json()
    with db_sessionmaker() as session:
        session.execute(update(Project).where(Project.project_id == "project").values(
            description="changed after review", updated_at=original_updated_at,
        ))
        session.commit()
    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200, login.text
    response = await agent_client.post(f"{path}/{proposal['change_request_id']}/approve-selected-operations",
        headers={"X-Space-Id": space}, json={"client_operation_ids": ["update"],
                                              "if_request_fingerprint": proposal["content_fingerprint"]})
    assert response.status_code == 409, response.text
    with db_sessionmaker() as session:
        assert session.get(Project, "project").description == "changed after review"
    refreshed = await agent_client.put(f"{path}/{proposal['change_request_id']}",
        headers=_auth_headers(token, space), json={
            "if_request_updated_at": proposal["updated_at"],
            "if_request_fingerprint": proposal["content_fingerprint"],
            "reason": proposal["reason"], "operations": proposal["operations"],
        })
    assert refreshed.status_code == 200, refreshed.text
    current = refreshed.json()
    assert current["content_fingerprint"] != proposal["content_fingerprint"]
    assert current["diff"][0]["fields"]["description"]["old"] == "changed after review"
    accepted = await agent_client.post(f"{path}/{proposal['change_request_id']}/approve-selected-operations",
        headers={"X-Space-Id": space}, json={"client_operation_ids": ["update"],
                                              "if_request_fingerprint": current["content_fingerprint"]})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "approved"
    with db_sessionmaker() as session:
        assert session.get(Project, "project").description == "proposed"


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_delegated_review_rejects_changed_content_with_same_timestamp(
    agent_client, db_sessionmaker, action  # noqa: F811
):
    from datetime import datetime
    from sqlalchemy import update
    from backend.app.models import AgentChangeRequest

    token, space = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space, soeid="reviewer", user_id="reviewer")
    path = "/project-manager/api/agent/change-requests"
    operation = {"client_operation_id": "create", "op": "create", "entity": "project", "fields": {"project_name": "First"}}
    submitted = await agent_client.post(path, headers=_auth_headers(token, space), json={
        "dry_run": False, "reason": "first", "idempotency_key": "delegated-same-time", "operations": [operation],
    })
    assert submitted.status_code == 201, submitted.text
    initial = submitted.json()
    request_id = initial["change_request_id"]
    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200
    delegated = await agent_client.post("/project-manager/api/agent/delegated-session")
    assert delegated.status_code == 200
    human = _auth_headers(delegated.json()["access_token"], space)
    reviewed = await agent_client.get(f"{path}/{request_id}/delegated-review", headers=human)
    assert reviewed.status_code == 200
    changed = await agent_client.put(f"{path}/{request_id}", headers=_auth_headers(token, space), json={
        "if_request_updated_at": initial["updated_at"], "if_request_fingerprint": initial["content_fingerprint"],
        "reason": "second", "operations": [{**operation, "fields": {"project_name": "Second"}}],
    })
    assert changed.status_code == 200, changed.text
    with db_sessionmaker() as session:
        session.execute(update(AgentChangeRequest).where(AgentChangeRequest.change_request_id == request_id).values(
            updated_at=datetime.fromisoformat(initial["updated_at"]),
        ))
        session.commit()
    stale = await agent_client.post(f"{path}/{request_id}/delegated-{action}", headers=human, json={
        "confirm_change_request_id": request_id, "if_request_updated_at": reviewed.json()["updated_at"],
        "if_request_fingerprint": reviewed.json()["content_fingerprint"],
    })
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "CHANGE_REQUEST_CHANGED"


@pytest.mark.anyio
async def test_bulk_review_requires_matching_fingerprints(agent_client, db_sessionmaker):  # noqa: F811
    token, space = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space, soeid="reviewer", user_id="reviewer")
    path = "/project-manager/api/agent/change-requests"
    submitted = await agent_client.post(path, headers=_auth_headers(token, space), json={
        "dry_run": False, "reason": "first", "idempotency_key": "bulk-review",
        "operations": [{"client_operation_id": "create", "op": "create", "entity": "project",
                        "fields": {"project_name": "First"}}],
    })
    assert submitted.status_code == 201, submitted.text
    proposal = submitted.json()
    request_id = proposal["change_request_id"]
    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200
    headers = {"X-Space-Id": space}
    missing = await agent_client.post(f"{path}/actions/approve-selected", headers=headers,
                                      json={"change_request_ids": [request_id]})
    assert missing.status_code == 422
    mismatch = await agent_client.post(f"{path}/actions/approve-selected", headers=headers, json={
        "change_request_ids": [request_id], "if_request_fingerprints": {request_id: "0" * 64},
    })
    assert mismatch.status_code == 409
    success = await agent_client.post(f"{path}/actions/approve-selected", headers=headers, json={
        "change_request_ids": [request_id], "if_request_fingerprints": {request_id: proposal["content_fingerprint"]},
    })
    assert success.status_code == 200, success.text
    assert success.json()["approved"] == 1


@pytest.mark.anyio
async def test_recover_changed_request_by_idempotency_key(agent_client, db_sessionmaker):  # noqa: F811
    token, space = _seed_agent_token(db_sessionmaker)
    headers = _auth_headers(token, space)
    path = "/project-manager/api/agent/change-requests"
    operation = {"client_operation_id": "create", "op": "create", "entity": "project", "fields": {"project_name": "Original"}}
    submitted = {"dry_run": False, "reason": "original", "idempotency_key": "recovery-key", "operations": [operation]}
    created = await agent_client.post(path, headers=headers, json=submitted)
    assert created.status_code == 201, created.text
    proposal = created.json()
    changed = await agent_client.put(f"{path}/{proposal['change_request_id']}", headers=headers, json={
        "if_request_updated_at": proposal["updated_at"], "if_request_fingerprint": proposal["content_fingerprint"],
        "reason": "updated", "operations": [operation],
    })
    assert changed.status_code == 200, changed.text
    replay = await agent_client.post(path, headers=headers, json=submitted)
    assert replay.status_code == 409, replay.text
    recovered = await agent_client.get(path, headers=headers, params={"status": "all", "idempotency_key": "recovery-key"})
    assert recovered.status_code == 200, recovered.text
    assert [item["change_request_id"] for item in recovered.json()["records"]] == [proposal["change_request_id"]]
    assert recovered.json()["records"][0]["reason"] == "updated"
