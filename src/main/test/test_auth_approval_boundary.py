from __future__ import annotations

import httpx
import pytest

from backend.app import deps
from backend.app.auth.auth import hash_password
from backend.app.models import ApiToken, Program, Project, Solution, Space, SpaceMembership, Team, User
from backend.app.services.api_tokens import hash_api_token
from backend.main import app


@pytest.fixture
async def approval_client(db_sessionmaker):
    token = "sipm_pat_approval-boundary-test"
    with db_sessionmaker() as session:
        space = Space(space_id="approval-space", name="Approval Space", slug="approval-space")
        admin = User(
            user_id="approval-admin", soeid="approvaladmin", email="admin@example.com",
            display_name="Admin", password_hash=hash_password("Password123"),
            role="global_admin", is_active=True,
        )
        target = User(
            user_id="approval-target", soeid="approvaltarget", email="target@example.com",
            display_name="Target", password_hash=hash_password("Password123"),
            role="user", is_active=True,
        )
        session.add_all([space, admin, target])
        session.flush()
        session.add_all([
            SpaceMembership(space_id=space.space_id, user_id=admin.user_id, role="space_admin", status="active"),
            SpaceMembership(space_id=space.space_id, user_id=target.user_id, role="member", status="active"),
            ApiToken(user_id=admin.user_id, name="test", token_hash=hash_api_token(token), created_by_user_id=admin.user_id),
            Program(program_id="approval-program", space_id=space.space_id, program_name="Program"),
            Project(project_id="approval-project", program_id="approval-program", space_id=space.space_id, project_name="Project"),
            Solution(solution_id="approval-solution", project_id="approval-project", space_id=space.space_id, solution_name="Solution"),
        ])
        session.commit()

    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[deps.get_db] = get_test_db
    try:
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                yield client, token
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("POST", "/teams", {"name": "New Team"}),
        ("PATCH", "/teams/team-id", {"name": "Renamed"}),
        ("DELETE", "/teams/team-id", None),
        ("POST", "/teams/team-id/members", {"member_name": "Member"}),
        ("PATCH", "/teams/team-id/members/member-id", {"member_name": "Renamed"}),
        ("DELETE", "/teams/team-id/members/member-id", None),
        ("POST", "/solutions/approval-solution/phases", {"phases": []}),
    ],
)
async def test_api_token_cannot_modify_team_or_solution_phases(approval_client, db_sessionmaker, method, path, payload):
    client, token = approval_client
    response = await client.request(
        method, f"/project-manager/api{path}", json=payload,
        headers={"Authorization": f"Bearer {token}", "X-Space-Id": "approval-space"},
    )
    assert response.status_code == 403, response.text
    assert response.headers["X-Error-Code"] == "AGENT_APPROVAL_REQUIRED"
    with db_sessionmaker() as session:
        assert session.query(Team).count() == 0


@pytest.mark.anyio
@pytest.mark.parametrize("target", ["approval-target", "by-soeid/approvaltarget"])
async def test_api_token_cannot_issue_interactive_password_reset(approval_client, db_sessionmaker, target):
    client, token = approval_client
    response = await client.post(
        f"/project-manager/api/users/{target}/password-reset-request",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403, response.text
    assert response.headers["X-Error-Code"] == "INTERACTIVE_USER_REQUIRED"
    with db_sessionmaker() as session:
        user = session.get(User, "approval-target")
        assert not user.force_password_reset
        assert user.temp_password_hash is None


@pytest.mark.anyio
async def test_interactive_admin_can_modify_shared_work_and_issue_password_reset(approval_client):
    client, _token = approval_client
    login = await client.post(
        "/project-manager/api/auth/login", json={"soeid": "approvaladmin", "password": "Password123"},
        headers={"X-Space-Id": "approval-space"},
    )
    assert login.status_code == 200, login.text
    headers = {"X-Space-Id": "approval-space"}
    team = await client.post("/project-manager/api/teams", headers=headers, json={"name": "New Team"})
    assert team.status_code == 201, team.text
    team_id = team.json()["team_id"]
    member = await client.post(
        f"/project-manager/api/teams/{team_id}/members", headers=headers, json={"member_name": "Member"},
    )
    assert member.status_code == 201, member.text
    member_id = member.json()["team_member_id"]
    changed_member = await client.patch(
        f"/project-manager/api/teams/{team_id}/members/{member_id}", headers=headers, json={"member_name": "Updated"},
    )
    assert changed_member.status_code == 200, changed_member.text
    removed_member = await client.delete(f"/project-manager/api/teams/{team_id}/members/{member_id}", headers=headers)
    assert removed_member.status_code == 204, removed_member.text
    changed_team = await client.patch(
        f"/project-manager/api/teams/{team_id}", headers=headers, json={"name": "Renamed Team"},
    )
    assert changed_team.status_code == 200, changed_team.text
    removed_team = await client.delete(f"/project-manager/api/teams/{team_id}", headers=headers)
    assert removed_team.status_code == 204, removed_team.text
    phases = await client.post(
        "/project-manager/api/solutions/approval-solution/phases", headers=headers, json={"phases": []},
    )
    assert phases.status_code == 200, phases.text
    reset = await client.post("/project-manager/api/users/approval-target/password-reset-request")
    assert reset.status_code == 201, reset.text
    assert reset.json()["temp_password"]
