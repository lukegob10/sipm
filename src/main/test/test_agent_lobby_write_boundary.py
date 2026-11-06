from __future__ import annotations

import httpx
import pytest

from backend.app import deps
from backend.app.auth.auth import hash_password
from backend.app.models import ApiToken, Program, Space, SpaceMembership, User
from backend.app.services.api_tokens import hash_api_token
from backend.main import app


@pytest.fixture
async def lobby_agent_client(db_sessionmaker):
    with db_sessionmaker() as session:
        user = User(user_id="lobby-user", soeid="lobbyuser", email="lobby@example.com",
                    display_name="Lobby User", password_hash=hash_password("Password123"), role="user", is_active=True)
        session.add_all([
            user,
            Space(space_id="home", name="Home", slug="home", space_kind="lobby", is_active=True),
            Space(space_id="work", name="Work", slug="work", space_kind="collaboration", is_active=True),
        ])
        session.flush()
        session.add_all([
            SpaceMembership(space_id=space_id, user_id=user.user_id, role="member", status="active")
            for space_id in ("home", "work")
        ])
        session.add(ApiToken(user_id=user.user_id, name="test", token_hash=hash_api_token("sipm_pat_lobby"),
                             created_by_user_id=user.user_id))
        session.commit()

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[deps.get_db] = get_test_db
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                login = await client.post("/project-manager/api/auth/login", json={"soeid": "lobbyuser", "password": "Password123"})
                assert login.status_code == 200, login.text
                delegated = await client.post("/project-manager/api/agent/delegated-session")
                assert delegated.status_code == 200, delegated.text
                yield client, delegated.json()["access_token"]
    finally:
        app.dependency_overrides.clear()


def _proposal(name):
    return {
        "reason": "Test change", "idempotency_key": name,
        "operations": [{"client_operation_id": "program", "op": "create", "entity": "program",
                        "fields": {"program_name": name}}],
    }


def _headers(token, space_id):
    return {"Authorization": f"Bearer {token}", "X-Space-Id": space_id}


async def _legacy_request(client, db_sessionmaker):
    with db_sessionmaker() as session:
        session.get(Space, "home").space_kind = "collaboration"
        session.commit()
    proposal = await client.post("/project-manager/api/agent/change-requests",
                                 headers=_headers("sipm_pat_lobby", "home"), json=_proposal("Legacy"))
    assert proposal.status_code == 201, proposal.text
    with db_sessionmaker() as session:
        session.get(Space, "home").space_kind = "lobby"
        session.commit()
    return proposal.json()


@pytest.mark.anyio
async def test_home_blocks_new_and_updated_proposals_but_allows_legacy_cancel(lobby_agent_client, db_sessionmaker):
    client, _delegated = lobby_agent_client
    denied = await client.post("/project-manager/api/agent/change-requests",
                               headers=_headers("sipm_pat_lobby", "home"), json=_proposal("Blocked"))
    assert denied.status_code == 400, denied.text
    assert denied.headers["X-Error-Code"] == "LOBBY_SPACE_READ_ONLY"
    legacy = await _legacy_request(client, db_sessionmaker)
    request_id = legacy["change_request_id"]
    update = await client.put(
        f"/project-manager/api/agent/change-requests/{request_id}",
        headers=_headers("sipm_pat_lobby", "home"),
        json={**_proposal("Changed"), "if_request_updated_at": legacy["updated_at"], "if_request_fingerprint": legacy["content_fingerprint"]},
    )
    assert update.status_code == 400, update.text
    assert update.headers["X-Error-Code"] == "LOBBY_SPACE_READ_ONLY"
    cancel = await client.post(f"/project-manager/api/agent/change-requests/{request_id}/cancel",
                               headers=_headers("sipm_pat_lobby", "home"))
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"


@pytest.mark.anyio
async def test_home_blocks_delegated_approval_but_allows_legacy_rejection(lobby_agent_client, db_sessionmaker):
    client, delegated = lobby_agent_client
    legacy = await _legacy_request(client, db_sessionmaker)
    request_id = legacy["change_request_id"]
    payload = {"confirm_change_request_id": request_id, "if_request_updated_at": legacy["updated_at"], "if_request_fingerprint": legacy["content_fingerprint"]}
    headers = _headers(delegated, "home")
    approval = await client.post(f"/project-manager/api/agent/change-requests/{request_id}/delegated-approve",
                                 headers=headers, json=payload)
    assert approval.status_code == 400, approval.text
    assert approval.headers["X-Error-Code"] == "LOBBY_SPACE_READ_ONLY"
    with db_sessionmaker() as session:
        assert session.query(Program).filter_by(space_id="home").count() == 0
    rejection = await client.post(f"/project-manager/api/agent/change-requests/{request_id}/delegated-reject",
                                  headers=headers, json=payload)
    assert rejection.status_code == 200, rejection.text
    assert rejection.json()["status"] == "rejected"


@pytest.mark.anyio
async def test_collaboration_proposal_and_delegated_approval_still_work(lobby_agent_client, db_sessionmaker):
    client, delegated = lobby_agent_client
    proposal = await client.post("/project-manager/api/agent/change-requests",
                                 headers=_headers("sipm_pat_lobby", "work"), json=_proposal("Allowed"))
    assert proposal.status_code == 201, proposal.text
    row = proposal.json()
    approval = await client.post(
        f"/project-manager/api/agent/change-requests/{row['change_request_id']}/delegated-approve",
        headers=_headers(delegated, "work"),
        json={"confirm_change_request_id": row["change_request_id"], "if_request_updated_at": row["updated_at"], "if_request_fingerprint": row["content_fingerprint"]},
    )
    assert approval.status_code == 200, approval.text
    assert approval.json()["status"] == "approved"
    with db_sessionmaker() as session:
        assert session.query(Program).filter_by(space_id="work", program_name="Allowed").count() == 1
