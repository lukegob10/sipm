from __future__ import annotations

import httpx
import pytest

from backend.app import deps as deps_module
from backend.app.auth.auth import hash_password
from backend.app.models import (
    AgentChangeRequest,
    ApiToken,
    ChangeLog,
    Program,
    Project,
    Space,
    SpaceMembership,
    Solution,
    Task,
    User,
)
from backend.app.services.api_tokens import TOKEN_PREFIX, hash_api_token
from backend.main import app as fastapi_app


@pytest.fixture
def override_db_only(db_sessionmaker):
    def get_test_db():
        with db_sessionmaker() as session:
            yield session

    fastapi_app.dependency_overrides[deps_module.get_db] = get_test_db
    try:
        yield
    finally:
        fastapi_app.dependency_overrides.clear()


@pytest.fixture
async def agent_client(override_db_only):
    async with fastapi_app.router.lifespan_context(fastapi_app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=fastapi_app),
            base_url="http://test",
        ) as client:
            yield client


def _seed_agent_token(
    db_sessionmaker,
    *,
    space_id: str = "space-a",
    role: str = "member",
    is_service_account: bool = True,
    is_active: bool = True,
) -> tuple[str, str]:
    raw_token = f"{TOKEN_PREFIX}test-token-{space_id}-{is_service_account}-{is_active}"
    with db_sessionmaker() as session:
        space = Space(space_id=space_id, name=f"Space {space_id}", slug=space_id)
        user = User(
            user_id=f"user-{space_id}-{is_service_account}-{is_active}",
            soeid=f"svc{space_id[-1]}",
            email=f"svc-{space_id}@example.com",
            display_name="Service Account",
            password_hash=hash_password("Password123"),
            role="user",
            is_active=is_active,
            is_service_account=is_service_account,
        )
        session.add_all([space, user])
        session.flush()
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=user.user_id,
                role=role,
                status="active",
            )
        )
        session.add(
            ApiToken(
                user_id=user.user_id,
                name="agent",
                token_hash=hash_api_token(raw_token),
                created_by_user_id=user.user_id,
            )
        )
        session.commit()
    return raw_token, space_id


def _seed_cookie_user(
    db_sessionmaker,
    *,
    space_id: str = "cookie-space",
    soeid: str = "cookie1",
    user_id: str = "cookie-user",
) -> tuple[str, str]:
    with db_sessionmaker() as session:
        space = session.query(Space).filter(Space.space_id == space_id).first()
        if space is None:
            space = Space(space_id=space_id, name=f"Space {space_id}", slug=space_id)
            session.add(space)
            session.flush()
        user = User(
            user_id=user_id,
            soeid=soeid,
            email=f"{soeid}@example.com",
            display_name="Cookie User",
            password_hash=hash_password("Password123"),
            role="user",
            is_active=True,
            is_service_account=False,
        )
        session.add_all([space, user])
        session.flush()
        session.add(
            SpaceMembership(
                space_id=space.space_id,
                user_id=user.user_id,
                role="member",
                status="active",
            )
        )
        session.commit()
    return soeid, space_id


def _auth_headers(token: str, space_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-Space-Id": space_id}


@pytest.mark.anyio
async def test_agent_auth_requires_bearer_service_account_and_space(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)

    no_space = await agent_client.get(
        "/project-manager/api/agent/work-graph",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert no_space.status_code == 403

    soeid, cookie_space_id = _seed_cookie_user(db_sessionmaker)
    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    cookie_auth = await agent_client.get(
        "/project-manager/api/agent/manifest",
        headers={"X-Space-Id": cookie_space_id},
    )
    assert cookie_auth.status_code == 401

    normal_token, normal_space_id = _seed_agent_token(
        db_sessionmaker, space_id="space-b", is_service_account=False
    )
    normal_user = await agent_client.get(
        "/project-manager/api/agent/manifest",
        headers=_auth_headers(normal_token, normal_space_id),
    )
    assert normal_user.status_code == 401

    accepted = await agent_client.get(
        "/project-manager/api/agent/manifest",
        headers=_auth_headers(token, space_id),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["writable_entities"] == [
        "program",
        "project",
        "solution",
        "task",
    ]


@pytest.mark.anyio
async def test_service_account_cannot_bypass_agent_approval_on_normal_solution_write(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    with db_sessionmaker() as session:
        program = Program(space_id=space_id, program_name="Default Program")
        session.add(program)
        session.flush()
        project = Project(
            space_id=space_id,
            program_id=program.program_id,
            project_name="HomeLab Server",
            status="active",
            sponsor="Owner",
            sponsor_user_soeid="own123",
            priority=1,
        )
        session.add(project)
        session.commit()
        project_id = project.project_id

    direct_write = await agent_client.post(
        f"/project-manager/api/projects/{project_id}/solutions",
        headers=_auth_headers(token, space_id),
        json={
            "solution_name": "Alpha",
            "version": "0.1.0",
            "status": "active",
            "rag_status": "green",
            "current_phase": "sandbox_deploy",
        },
    )
    assert direct_write.status_code == 403
    assert direct_write.headers["X-Error-Code"] == "AGENT_APPROVAL_REQUIRED"

    queued = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "Queue Alpha for approval",
            "idempotency_key": "alpha-approval-required",
            "operations": [
                {
                    "client_operation_id": "create-alpha",
                    "op": "create",
                    "entity": "solution",
                    "project_id": project_id,
                    "fields": {
                        "solution_name": "Alpha",
                        "version": "0.1.0",
                        "status": "active",
                        "rag_status": "green",
                    },
                }
            ],
        },
    )
    assert queued.status_code == 201, queued.text
    assert queued.json()["status"] == "pending"
    with db_sessionmaker() as session:
        assert (
            session.query(Solution)
            .filter(Solution.project_id == project_id)
            .filter(Solution.solution_name == "Alpha")
            .first()
            is None
        )


def _seed_work_graph(db_sessionmaker):
    token, space_id = _seed_agent_token(db_sessionmaker)
    other_token, other_space_id = _seed_agent_token(db_sessionmaker, space_id="space-z")
    with db_sessionmaker() as session:
        program = Program(space_id=space_id, program_name="Default Program")
        other_program = Program(space_id=other_space_id, program_name="Default Program")
        session.add_all([program, other_program])
        session.flush()
        project = Project(
            space_id=space_id,
            program_id=program.program_id,
            project_name="Agent Project",
            status="active",
            sponsor="Sponsor",
            priority=2,
        )
        other_project = Project(
            space_id=other_space_id,
            program_id=other_program.program_id,
            project_name="Other Project",
            status="active",
            sponsor="Sponsor",
        )
        session.add_all([project, other_project])
        session.flush()
        solution = Solution(
            space_id=space_id,
            project_id=project.project_id,
            solution_name="Agent Solution",
            version="1.0.0",
            status="active",
            rag_status="green",
            priority=1,
            owner="Owner",
            owner_user_soeid="own123",
            assignee="Assignee",
            assignee_user_soeid="assn123",
        )
        session.add(solution)
        session.flush()
        task = Task(
            space_id=space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Agent Task",
            status="in_progress",
            priority=1,
            assignee="Worker",
            assignee_user_soeid="wrk123",
        )
        session.add(task)
        session.commit()
        project_id = project.project_id
        solution_id = solution.solution_id
        task_id = task.task_id
        project_updated_at = project.updated_at.isoformat()
        solution_updated_at = solution.updated_at.isoformat()
        task_updated_at = task.updated_at.isoformat()
    return (
        token,
        space_id,
        other_token,
        other_space_id,
        project_id,
        solution_id,
        task_id,
        project_updated_at,
        solution_updated_at,
        task_updated_at,
    )


@pytest.mark.anyio
async def test_agent_work_graph_is_scoped_nested_and_filterable(
    agent_client, db_sessionmaker
):
    token, space_id, _other_token, _other_space_id, project_id, solution_id, *_ = (
        _seed_work_graph(db_sessionmaker)
    )

    response = await agent_client.get(
        "/project-manager/api/agent/work-graph",
        headers=_auth_headers(token, space_id),
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["space_id"] == space_id
    assert [row["program_name"] for row in data["programs"]] == ["Default Program"]
    assert [row["project_name"] for row in data["records"]] == ["Agent Project"]
    solution = data["records"][0]["solutions"][0]
    assert solution["solution_id"] == solution_id
    assert solution["tasks"][0]["task_name"] == "Agent Task"

    owner_filter = await agent_client.get(
        "/project-manager/api/agent/work-graph?owner_user_soeid=own123",
        headers=_auth_headers(token, space_id),
    )
    assert owner_filter.status_code == 200, owner_filter.text
    assert owner_filter.json()["records"][0]["project_id"] == project_id

    missing_filter = await agent_client.get(
        "/project-manager/api/agent/work-graph?assignee_user_soeid=missing",
        headers=_auth_headers(token, space_id),
    )
    assert missing_filter.status_code == 200, missing_filter.text
    assert missing_filter.json()["records"] == []


@pytest.mark.anyio
async def test_agent_patch_validation_rejects_uncontrolled_changes_without_mutation(
    agent_client, db_sessionmaker
):
    token, space_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        before_count = session.query(Project).count()

    payload = {
        "dry_run": True,
        "operations": [
            {
                "client_operation_id": "one",
                "op": "delete",
                "entity": "project",
                "id": "anything",
                "fields": {"project_name": "Bad"},
            },
            {
                "client_operation_id": "one",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Valid Name"},
            },
            {
                "client_operation_id": "three",
                "op": "create",
                "entity": "project",
                "fields": {"space_id": "other", "project_name": "Bad Field"},
            },
        ],
    }
    response = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers=_auth_headers(token, space_id),
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is False
    codes = [result["code"] for result in body["results"]]
    assert codes == ["OP_NOT_ALLOWED", "DUPLICATE_OPERATION_ID", "FIELD_NOT_ALLOWED"]

    with db_sessionmaker() as session:
        assert session.query(Project).count() == before_count


@pytest.mark.anyio
async def test_agent_patch_validation_accepts_allowed_entities_and_rejects_stale_or_cross_space(
    agent_client, db_sessionmaker
):
    (
        token,
        space_id,
        _other_token,
        other_space_id,
        project_id,
        solution_id,
        task_id,
        project_updated_at,
        solution_updated_at,
        task_updated_at,
    ) = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        other_project = session.query(Project).filter(Project.space_id == other_space_id).one()
        program = session.query(Program).filter(Program.space_id == space_id).one()
        program_id = program.program_id
        program_updated_at = program.updated_at.isoformat()

    valid_payload = {
        "dry_run": True,
        "operations": [
            {
                "client_operation_id": "program-update",
                "op": "update",
                "entity": "program",
                "id": program_id,
                "if_updated_at": program_updated_at,
                "fields": {"description": "Validated program only"},
            },
            {
                "client_operation_id": "program-create",
                "op": "create",
                "entity": "program",
                "fields": {
                    "program_name": "New Agent Program",
                    "description": "Validated only",
                },
            },
            {
                "client_operation_id": "project-update",
                "op": "update",
                "entity": "project",
                "id": project_id,
                "if_updated_at": project_updated_at,
                "fields": {"description": "Validated only"},
            },
            {
                "client_operation_id": "solution-update",
                "op": "update",
                "entity": "solution",
                "id": solution_id,
                "if_updated_at": solution_updated_at,
                "fields": {"rag_status": "amber", "rag_reason": "Needs review"},
            },
            {
                "client_operation_id": "task-update",
                "op": "update",
                "entity": "task",
                "id": task_id,
                "if_updated_at": task_updated_at,
                "fields": {"blocked": True, "blocker_note": "Waiting"},
            },
            {
                "client_operation_id": "solution-create",
                "op": "create",
                "entity": "solution",
                "project_id": project_id,
                "fields": {"solution_name": "New Agent Solution"},
            },
            {
                "client_operation_id": "task-create",
                "op": "create",
                "entity": "task",
                "solution_id": solution_id,
                "fields": {"task_name": "New Agent Task"},
            },
        ],
    }
    valid = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers=_auth_headers(token, space_id),
        json=valid_payload,
    )
    assert valid.status_code == 200, valid.text
    assert valid.json()["valid"] is True

    invalid_payload = {
        "dry_run": True,
        "operations": [
            {
                "client_operation_id": "unknown-entity",
                "op": "create",
                "entity": "team",
                "fields": {"name": "No"},
            },
            {
                "client_operation_id": "stale",
                "op": "update",
                "entity": "project",
                "id": project_id,
                "if_updated_at": "2000-01-01T00:00:00",
                "fields": {"description": "Stale"},
            },
            {
                "client_operation_id": "cross-space",
                "op": "update",
                "entity": "project",
                "id": other_project.project_id,
                "if_updated_at": other_project.updated_at.isoformat(),
                "fields": {"description": "Wrong space"},
            },
        ],
    }
    invalid = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers=_auth_headers(token, space_id),
        json=invalid_payload,
    )
    assert invalid.status_code == 200, invalid.text
    body = invalid.json()
    assert body["valid"] is False
    assert [result["code"] for result in body["results"]] == [
        "ENTITY_NOT_ALLOWED",
        "STALE_ENTITY",
        "PROJECT_NOT_FOUND",
    ]


@pytest.mark.anyio
async def test_agent_program_read_endpoints_are_service_account_scoped(
    agent_client, db_sessionmaker
):
    token, space_id, other_token, other_space_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        program = session.query(Program).filter(Program.space_id == space_id).one()
        other_program = session.query(Program).filter(Program.space_id == other_space_id).one()

    no_bearer = await agent_client.get(
        "/project-manager/api/agent/programs",
        headers={"X-Space-Id": space_id},
    )
    assert no_bearer.status_code == 401

    listing = await agent_client.get(
        "/project-manager/api/agent/programs",
        headers=_auth_headers(token, space_id),
    )
    assert listing.status_code == 200, listing.text
    assert [row["program_name"] for row in listing.json()] == ["Default Program"]

    detail = await agent_client.get(
        f"/project-manager/api/agent/programs/{program.program_id}",
        headers=_auth_headers(token, space_id),
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["program_id"] == program.program_id

    cross_space_detail = await agent_client.get(
        f"/project-manager/api/agent/programs/{other_program.program_id}",
        headers=_auth_headers(token, space_id),
    )
    assert cross_space_detail.status_code == 404

    other_space_listing = await agent_client.get(
        "/project-manager/api/agent/programs",
        headers=_auth_headers(other_token, other_space_id),
    )
    assert other_space_listing.status_code == 200, other_space_listing.text
    assert [row["program_id"] for row in other_space_listing.json()] == [
        other_program.program_id
    ]


@pytest.mark.anyio
async def test_agent_program_patch_validation_rejects_bad_names_stale_and_cross_space(
    agent_client, db_sessionmaker
):
    token, space_id, _other_token, other_space_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        program = session.query(Program).filter(Program.space_id == space_id).one()
        other_program = session.query(Program).filter(Program.space_id == other_space_id).one()

    payload = {
        "dry_run": True,
        "operations": [
            {
                "client_operation_id": "bad-field",
                "op": "create",
                "entity": "program",
                "fields": {"program_name": "Bad Field", "space_id": "wrong"},
            },
            {
                "client_operation_id": "empty-name",
                "op": "create",
                "entity": "program",
                "fields": {"program_name": "   "},
            },
            {
                "client_operation_id": "duplicate-name",
                "op": "create",
                "entity": "program",
                "fields": {"program_name": program.program_name},
            },
            {
                "client_operation_id": "stale-program",
                "op": "update",
                "entity": "program",
                "id": program.program_id,
                "if_updated_at": "2000-01-01T00:00:00",
                "fields": {"description": "Stale"},
            },
            {
                "client_operation_id": "cross-space-program",
                "op": "update",
                "entity": "program",
                "id": other_program.program_id,
                "if_updated_at": other_program.updated_at.isoformat(),
                "fields": {"description": "Wrong space"},
            },
        ],
    }

    response = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers=_auth_headers(token, space_id),
        json=payload,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["valid"] is False
    assert [result["code"] for result in body["results"]] == [
        "FIELD_NOT_ALLOWED",
        "PROGRAM_NAME_REQUIRED",
        "PROGRAM_NAME_CONFLICT",
        "STALE_ENTITY",
        "PROGRAM_NOT_FOUND",
    ]


@pytest.mark.anyio
async def test_agent_change_request_approval_applies_and_audits(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="member1",
        user_id="member-user",
    )
    direct_apply = await agent_client.post(
        "/project-manager/api/agent/patches/apply",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "direct apply is blocked",
            "idempotency_key": "direct-1",
            "operations": [
                {
                    "client_operation_id": "create-project",
                    "op": "create",
                    "entity": "project",
                    "fields": {"project_name": "Blocked Direct Apply"},
                }
            ],
        },
    )
    assert direct_apply.status_code == 403
    assert direct_apply.headers["X-Error-Code"] == "AGENT_APPROVAL_REQUIRED"

    submit_payload = {
        "dry_run": False,
        "reason": "create controlled work items",
        "idempotency_key": "approval-1",
        "operations": [
            {
                "client_operation_id": "create-project",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Created By Approval", "status": "active"},
            }
        ],
    }
    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=submit_payload,
    )
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["change_request_id"]
    assert submitted.json()["status"] == "pending"
    assert submitted.json()["diff"][0]["fields"]["project_name"]["new"] == "Created By Approval"

    service_account_approval = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/approve",
        headers=_auth_headers(token, space_id),
        json={},
    )
    assert service_account_approval.status_code == 403

    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    pending = await agent_client.get(
        "/project-manager/api/agent/change-requests",
        headers={"X-Space-Id": space_id},
    )
    assert pending.status_code == 200, pending.text
    assert pending.json()["pending_count"] == 1

    approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/approve",
        headers={"X-Space-Id": space_id},
        json={"review_note": "Looks good"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    with db_sessionmaker() as session:
        project = (
            session.query(Project)
            .filter(Project.project_name == "Created By Approval")
            .one()
        )
        assert (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "project")
            .filter(ChangeLog.entity_id == project.project_id)
            .count()
            > 0
        )


@pytest.mark.anyio
async def test_agent_program_change_request_approval_applies_and_audits(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="member3",
        user_id="member-user-3",
    )
    create_payload = {
        "dry_run": False,
        "reason": "create controlled program",
        "idempotency_key": "program-create-approval-1",
        "operations": [
            {
                "client_operation_id": "create-program",
                "op": "create",
                "entity": "program",
                "fields": {
                    "program_name": "Agent Program",
                    "description": "Created through approval",
                },
            }
        ],
    }

    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=create_payload,
    )
    assert submitted.status_code == 201, submitted.text
    retry = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=create_payload,
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["change_request_id"] == submitted.json()["change_request_id"]
    assert submitted.json()["status"] == "pending"
    assert submitted.json()["diff"][0]["fields"]["program_name"]["new"] == "Agent Program"
    with db_sessionmaker() as session:
        assert session.query(Program).filter(Program.program_name == "Agent Program").first() is None

    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{submitted.json()['change_request_id']}/approve",
        headers={"X-Space-Id": space_id},
        json={"review_note": "Create program"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    with db_sessionmaker() as session:
        program = session.query(Program).filter(Program.program_name == "Agent Program").one()
        program_id = program.program_id
        program_updated_at = program.updated_at.isoformat()
        assert (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "program")
            .filter(ChangeLog.entity_id == program_id)
            .filter(ChangeLog.action == "create")
            .count()
            > 0
        )

    update_payload = {
        "dry_run": False,
        "reason": "rename controlled program",
        "idempotency_key": "program-update-approval-1",
        "operations": [
            {
                "client_operation_id": "update-program",
                "op": "update",
                "entity": "program",
                "id": program_id,
                "if_updated_at": program_updated_at,
                "fields": {
                    "program_name": "Agent Program Renamed",
                    "description": "Updated through approval",
                },
            }
        ],
    }
    update_submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=update_payload,
    )
    assert update_submitted.status_code == 201, update_submitted.text
    assert update_submitted.json()["diff"][0]["entity_label"] == "Agent Program"

    update_approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{update_submitted.json()['change_request_id']}/approve",
        headers={"X-Space-Id": space_id},
        json={"review_note": "Rename program"},
    )
    assert update_approved.status_code == 200, update_approved.text
    assert update_approved.json()["status"] == "approved"
    with db_sessionmaker() as session:
        program = session.query(Program).filter(Program.program_id == program_id).one()
        assert program.program_name == "Agent Program Renamed"
        assert program.description == "Updated through approval"
        assert (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "program")
            .filter(ChangeLog.entity_id == program_id)
            .filter(ChangeLog.action == "update")
            .count()
            > 0
        )


@pytest.mark.anyio
async def test_agent_change_request_idempotency_key_deduplicates_retry(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    payload = {
        "dry_run": False,
        "reason": "create once",
        "idempotency_key": "same-key",
        "operations": [
            {
                "client_operation_id": "create-project",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Created Once", "status": "active"},
            }
        ],
    }

    first = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=payload,
    )
    assert first.status_code == 201, first.text
    retry = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=payload,
    )
    assert retry.status_code == 201, retry.text
    assert retry.json()["change_request_id"] == first.json()["change_request_id"]

    changed_payload = {
        **payload,
        "operations": [
            {
                "client_operation_id": "create-project",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Different Project", "status": "active"},
            }
        ],
    }
    conflict = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=changed_payload,
    )
    assert conflict.status_code == 409

    with db_sessionmaker() as session:
        assert session.query(AgentChangeRequest).count() == 1


@pytest.mark.anyio
async def test_agent_change_request_reject_and_stale_failure(
    agent_client, db_sessionmaker
):
    seeded = _seed_work_graph(db_sessionmaker)
    token = seeded[0]
    space_id = seeded[1]
    project_id = seeded[4]
    project_updated_at = seeded[7]
    soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="member2",
        user_id="member-user-2",
    )
    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text

    rejected = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "reject me",
            "idempotency_key": "reject-1",
            "operations": [
                {
                    "client_operation_id": "reject-project",
                    "op": "create",
                    "entity": "project",
                    "fields": {"project_name": "Rejected Project"},
                }
            ],
        },
    )
    assert rejected.status_code == 201, rejected.text
    reject_id = rejected.json()["change_request_id"]
    reject_resp = await agent_client.post(
        "/project-manager/api/agent/change-requests/actions/reject-selected",
        headers={"X-Space-Id": space_id},
        json={"change_request_ids": [reject_id], "review_note": "No"},
    )
    assert reject_resp.status_code == 200, reject_resp.text
    assert reject_resp.json()["rejected"] == 1
    pending_after_reject = await agent_client.get(
        "/project-manager/api/agent/change-requests",
        headers={"X-Space-Id": space_id},
    )
    assert pending_after_reject.json()["pending_count"] == 0

    stale = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "will go stale",
            "idempotency_key": "stale-1",
            "operations": [
                {
                    "client_operation_id": "stale-project",
                    "op": "update",
                    "entity": "project",
                    "id": project_id,
                    "if_updated_at": project_updated_at,
                    "fields": {"description": "Should fail stale"},
                }
            ],
        },
    )
    assert stale.status_code == 201, stale.text
    stale_id = stale.json()["change_request_id"]
    with db_sessionmaker() as session:
        project = session.query(Project).filter(Project.project_id == project_id).one()
        project.description = "Changed elsewhere"
        session.add(project)
        session.commit()
    stale_approval = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{stale_id}/approve",
        headers={"X-Space-Id": space_id},
        json={},
    )
    assert stale_approval.status_code == 200, stale_approval.text
    assert stale_approval.json()["status"] == "failed"
    with db_sessionmaker() as session:
        row = (
            session.query(AgentChangeRequest)
            .filter(AgentChangeRequest.change_request_id == stale_id)
            .one()
        )
        assert row.status == "failed"
        project = session.query(Project).filter(Project.project_id == project_id).one()
        assert project.description == "Changed elsewhere"
