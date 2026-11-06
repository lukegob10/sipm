import pytest

from test_agent_api import _auth_headers, _seed_agent_token, _seed_cookie_user, agent_client, override_db_only  # noqa: F401
from backend.app.models import AgentChangeRequest, Project


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["approve", "reject"])
async def test_bulk_review_rolls_back_when_later_fingerprint_is_stale(agent_client, db_sessionmaker, action):  # noqa: F811
    token, space = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space, soeid="reviewer", user_id="reviewer")
    path = "/project-manager/api/agent/change-requests"
    proposals = []
    for index in range(2):
        response = await agent_client.post(path, headers=_auth_headers(token, space), json={
            "dry_run": False, "reason": "bulk", "idempotency_key": f"bulk-{index}",
            "operations": [{"client_operation_id": "create", "op": "create", "entity": "project",
                            "fields": {"project_name": f"Bulk {index}"}}],
        })
        assert response.status_code == 201, response.text
        proposals.append(response.json())
    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200
    ids = [item["change_request_id"] for item in proposals]
    response = await agent_client.post(f"{path}/actions/{action}-selected", headers={"X-Space-Id": space}, json={
        "change_request_ids": ids,
        "if_request_fingerprints": {ids[0]: proposals[0]["content_fingerprint"], ids[1]: "0" * 64},
    })
    assert response.status_code == 409, response.text
    with db_sessionmaker() as session:
        assert [session.get(AgentChangeRequest, item).status for item in ids] == ["pending", "pending"]
        assert session.query(Project).filter(Project.project_name.in_(["Bulk 0", "Bulk 1"])).count() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("action", ["approve", "reject"])
@pytest.mark.parametrize("fail_after_first", [False, True])
async def test_bulk_review_commits_together_or_rolls_back_after_first(
    agent_client, db_sessionmaker, monkeypatch, action, fail_after_first  # noqa: F811
):
    from backend.app.services import agent_change_requests as service

    token, space = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space, soeid="reviewer", user_id="reviewer")
    path = "/project-manager/api/agent/change-requests"
    proposals = []
    for index in range(2):
        response = await agent_client.post(path, headers=_auth_headers(token, space), json={
            "dry_run": False, "reason": "bulk", "idempotency_key": f"atomic-{index}",
            "operations": [{"client_operation_id": "create", "op": "create", "entity": "project",
                            "fields": {"project_name": f"Atomic {index}"}}],
        })
        assert response.status_code == 201, response.text
        proposals.append(response.json())
    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200

    published = []
    monkeypatch.setattr(service, "_publish_change_requests", lambda *args: published.append("requests"))
    monkeypatch.setattr(service, "publish_patch_plan_mutations", lambda *args: published.append("patch"))
    if fail_after_first:
        name = f"{action}_change_request"
        original = getattr(service, name)
        calls = 0

        def fail_on_second(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("simulated failure after first decision")
            return original(*args, **kwargs)

        monkeypatch.setattr(service, name, fail_on_second)

    ids = [item["change_request_id"] for item in proposals]
    payload = {"change_request_ids": ids, "if_request_fingerprints": {
        item["change_request_id"]: item["content_fingerprint"] for item in proposals
    }}
    if fail_after_first:
        with pytest.raises(RuntimeError, match="simulated failure"):
            await agent_client.post(f"{path}/actions/{action}-selected", headers={"X-Space-Id": space}, json=payload)
        expected_status = "pending"
        assert published == []
    else:
        response = await agent_client.post(f"{path}/actions/{action}-selected", headers={"X-Space-Id": space}, json=payload)
        assert response.status_code == 200, response.text
        expected_status = "approved" if action == "approve" else "rejected"
        assert response.json()[expected_status] == 2
        assert published.count("requests") == 1
        assert published.count("patch") == (2 if action == "approve" else 0)

    with db_sessionmaker() as session:
        assert [session.get(AgentChangeRequest, item).status for item in ids] == [expected_status] * 2
        count = session.query(Project).filter(Project.project_name.in_(["Atomic 0", "Atomic 1"])).count()
        assert count == (2 if expected_status == "approved" else 0)
