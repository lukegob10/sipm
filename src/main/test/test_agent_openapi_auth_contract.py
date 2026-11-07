from __future__ import annotations

import pytest

from test_agent_api import _seed_agent_token, _seed_cookie_user, agent_client, override_db_only  # noqa: F401


def _operation(document, suffix, method):
    return document["paths"][f"/project-manager/api/agent{suffix}"][method]


def _space_header(operation):
    return next(parameter for parameter in operation.get("parameters", []) if parameter.get("name") == "X-Space-Id")


@pytest.mark.anyio
async def test_agent_openapi_matches_cookie_pat_and_delegated_review_auth(agent_client, db_sessionmaker):  # noqa: F811
    token, space_id = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(db_sessionmaker, space_id=space_id, soeid="openapi-reviewer", user_id="openapi-reviewer")
    schema_response = await agent_client.get("/project-manager/api/agent/openapi.json", headers={"Authorization": f"Bearer {token}"})
    assert schema_response.status_code == 200, schema_response.text
    document = schema_response.json()
    cookie = [{"HumanSessionCookie": []}]
    api_or_cookie = [{"AgentBearer": []}, {"HumanSessionCookie": []}]
    delegated = [{"HumanDelegatedBearer": []}]

    for suffix in ("/change-requests", "/change-requests/{change_request_id}"):
        operation = _operation(document, suffix, "get")
        assert operation["security"] == api_or_cookie
        assert _space_header(operation)["required"] is False
    for suffix in ("/change-requests/{change_request_id}/approve", "/change-requests/{change_request_id}/reject",
                   "/change-requests/{change_request_id}/approve-selected-operations",
                   "/change-requests/actions/approve-selected", "/change-requests/actions/reject-selected"):
        operation = _operation(document, suffix, "post")
        assert operation["security"] == cookie
        assert _space_header(operation)["required"] is False
    for suffix, method in (("/change-requests/{change_request_id}/delegated-review", "get"),
                           ("/change-requests/{change_request_id}/delegated-approve", "post"),
                           ("/change-requests/{change_request_id}/delegated-reject", "post")):
        operation = _operation(document, suffix, method)
        assert operation["security"] == delegated
        assert _space_header(operation)["required"] is True
    assert _operation(document, "/delegated-session", "post")["security"] == cookie
    assert _operation(document, "/projects/{project_id}", "get")["security"] == [{"AgentBearer": []}]
    assert _space_header(_operation(document, "/projects/{project_id}", "get"))["required"] is True

    login = await agent_client.post("/project-manager/api/auth/login", json={"soeid": soeid, "password": "Password123"})
    assert login.status_code == 200, login.text
    cookie_list = await agent_client.get("/project-manager/api/agent/change-requests")
    assert cookie_list.status_code == 200, cookie_list.text
    no_space = await agent_client.get("/project-manager/api/agent/change-requests", headers={"Authorization": f"Bearer {token}"})
    assert no_space.status_code == 403
    bearer_approve = await agent_client.post("/project-manager/api/agent/change-requests/missing/approve",
                                             headers={"Authorization": f"Bearer {token}", "X-Space-Id": space_id})
    assert bearer_approve.status_code == 403
    cookie_approve = await agent_client.post("/project-manager/api/agent/change-requests/missing/approve",
                                              json={"if_request_fingerprint": "0" * 64})
    assert cookie_approve.status_code == 404
    delegated_token = await agent_client.post("/project-manager/api/agent/delegated-session")
    assert delegated_token.status_code == 200, delegated_token.text
    delegated_headers = {"Authorization": f"Bearer {delegated_token.json()['access_token']}", "X-Space-Id": space_id}
    delegated_review = await agent_client.get("/project-manager/api/agent/change-requests/missing/delegated-review", headers=delegated_headers)
    assert delegated_review.status_code == 404
    cookie_review = await agent_client.get("/project-manager/api/agent/change-requests/missing/delegated-review")
    assert cookie_review.status_code == 401
