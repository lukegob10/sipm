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
    Team,
    TeamMember,
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


def _seed_additional_agent_token(
    db_sessionmaker,
    *,
    space_id: str,
    user_id: str,
    is_service_account: bool = True,
) -> str:
    raw_token = f"{TOKEN_PREFIX}test-token-{user_id}"
    with db_sessionmaker() as session:
        user = User(
            user_id=user_id,
            soeid=user_id,
            email=f"{user_id}@example.com",
            display_name=f"Service Account {user_id}",
            password_hash=hash_password("Password123"),
            role="user",
            is_active=True,
            is_service_account=is_service_account,
        )
        session.add(user)
        session.flush()
        session.add_all(
            [
                SpaceMembership(
                    space_id=space_id,
                    user_id=user.user_id,
                    role="member",
                    status="active",
                ),
                ApiToken(
                    user_id=user.user_id,
                    name="agent",
                    token_hash=hash_api_token(raw_token),
                    created_by_user_id=user.user_id,
                ),
            ]
        )
        session.commit()
    return raw_token


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
        headers={"Authorization": f"Bearer {token}"},
    )
    assert accepted.status_code == 200, accepted.text
    manifest = accepted.json()
    assert manifest["version"] == "1.4"
    assert manifest["capabilities"] == [
        "read_programs",
        "read_spaces",
        "read_work_graph",
        "read_paginated_work_graph",
        "read_work_item_details",
        "read_assigned_work",
        "search_work_items",
        "read_own_change_requests",
        "cancel_own_change_request",
        "update_own_pending_change_request",
        "archive_work_items",
        "human_delegated_review",
        "read_audit_feed",
        "read_reference_data",
        "read_agent_openapi",
        "read_people_and_teams",
        "validate_patch",
        "submit_change_request",
    ]
    assert "apply_patch" not in manifest["capabilities"]
    assert manifest["writable_entities"] == [
        "program",
        "project",
        "solution",
        "task",
    ]
    assert manifest["writable_actions"] == ["archive", "create", "update"]
    assert manifest["writes_require_change_request"] is True
    assert manifest["human_review_required"] is True
    assert manifest["service_account_can_approve"] is False
    assert manifest["human_delegated_review"] is True
    assert manifest["max_patch_operations"] == 25
    assert manifest["requires_space_id"] is True
    assert manifest["space_discovery_requires_space_id"] is False
    assert manifest["space_discovery_path"] == "/api/agent/spaces"


@pytest.mark.anyio
async def test_agent_space_discovery_is_accessible_paginated_and_scoped(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    user_id = f"user-{space_id}-True-True"
    accessible_ids = {space_id}
    with db_sessionmaker() as session:
        for index in range(5):
            extra_space_id = f"agent-space-{index}"
            accessible_ids.add(extra_space_id)
            session.add(
                Space(
                    space_id=extra_space_id,
                    name=f"Workspace {index:02d}",
                    slug=f"workspace-{index:02d}",
                )
            )
            session.flush()
            session.add(
                SpaceMembership(
                    space_id=extra_space_id,
                    user_id=user_id,
                    role="member",
                    status="active",
                )
            )
        session.add(
            Space(
                space_id="inaccessible-space",
                name="Inaccessible Workspace",
                slug="inaccessible-workspace",
            )
        )
        session.commit()

    headers = {"Authorization": f"Bearer {token}"}
    discovered_ids: list[str] = []
    cursor = None
    while True:
        response = await agent_client.get(
            "/project-manager/api/agent/spaces",
            headers=headers,
            params={
                "limit": 2,
                **({"cursor": cursor} if cursor else {}),
            },
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert len(body["records"]) <= 2
        discovered_ids.extend(row["space_id"] for row in body["records"])
        if not body["has_more"]:
            assert body["next_cursor"] is None
            break
        cursor = body.get("next_cursor")
        assert cursor

    assert len(discovered_ids) == len(set(discovered_ids))
    assert set(discovered_ids) == accessible_ids
    assert "inaccessible-space" not in discovered_ids

    by_slug = await agent_client.get(
        "/project-manager/api/agent/spaces",
        headers=headers,
        params={"slug": "workspace-03"},
    )
    assert by_slug.status_code == 200, by_slug.text
    assert [row["space_id"] for row in by_slug.json()["records"]] == ["agent-space-3"]

    detail = await agent_client.get(
        "/project-manager/api/agent/spaces/agent-space-3",
        headers=headers,
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["slug"] == "workspace-03"
    assert detail.json()["role"] == "member"

    inaccessible_detail = await agent_client.get(
        "/project-manager/api/agent/spaces/inaccessible-space",
        headers=headers,
    )
    assert inaccessible_detail.status_code == 404
    assert inaccessible_detail.json()["code"] == "SPACE_NOT_FOUND"

    tampered = await agent_client.get(
        "/project-manager/api/agent/spaces",
        headers=headers,
        params={"limit": 2, "cursor": f"{cursor}x"},
    )
    assert tampered.status_code == 400
    assert tampered.json()["code"] == "INVALID_CURSOR"


@pytest.mark.anyio
async def test_agent_errors_use_stable_envelope_and_request_id(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)

    unauthenticated = await agent_client.get(
        "/project-manager/api/agent/manifest",
        headers={"X-Space-Id": space_id, "X-Request-ID": "agent-auth-error"},
    )
    assert unauthenticated.status_code == 401
    assert unauthenticated.headers["X-Error-Code"] == "AUTH_REQUIRED"
    assert unauthenticated.json() == {
        "code": "AUTH_REQUIRED",
        "message": "Bearer API token required",
        "request_id": "agent-auth-error",
        "details": {},
    }

    invalid_payload = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers={
            **_auth_headers(token, space_id),
            "X-Request-ID": "agent-validation-error",
        },
        json={"dry_run": True},
    )
    assert invalid_payload.status_code == 422
    assert invalid_payload.headers["X-Error-Code"] == "REQUEST_VALIDATION_ERROR"
    validation_error = invalid_payload.json()
    assert validation_error["code"] == "REQUEST_VALIDATION_ERROR"
    assert validation_error["message"] == "Agent request validation failed"
    assert validation_error["request_id"] == "agent-validation-error"
    assert validation_error["details"]["errors"][0]["loc"] == [
        "body",
        "operations",
    ]


@pytest.mark.anyio
async def test_non_agent_errors_keep_fastapi_response_shape(client):
    response = await client.get("/project-manager/api/projects/missing-project")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project not found"}
    assert "X-Error-Code" not in response.headers


@pytest.mark.anyio
async def test_service_account_cannot_bypass_agent_approval_on_normal_solution_write(
    agent_client, db_sessionmaker, monkeypatch
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    publish_calls = []

    def capture_publish(space_id_arg, cache_keys, *, broadcast_channel=None):
        publish_calls.append(
            {
                "space_id": space_id_arg,
                "cache_keys": list(cache_keys),
                "broadcast_channel": broadcast_channel,
            }
        )

    monkeypatch.setattr(
        "backend.app.services.agent_change_requests.publish_space_mutation",
        capture_publish,
    )
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
    assert publish_calls == [
        {
            "space_id": space_id,
            "cache_keys": ["agent_change_requests"],
            "broadcast_channel": "agent_change_requests",
        }
    ]
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
            owner="Project Owner",
            owner_user_soeid="project-owner",
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
async def test_agent_assigned_work_is_shared_scoped_paginated_and_private_state_free(
    agent_client, db_sessionmaker
):
    token, space_id, _other_token, _other_space_id, _project_id, solution_id, task_id, *_ = (
        _seed_work_graph(db_sessionmaker)
    )
    with db_sessionmaker() as session:
        solution = session.get(Solution, solution_id)
        solution.github_repo_url = "https://github.com/example/assigned-work"
        attention_task = session.get(Task, task_id)
        attention_task.blocked = True
        attention_task.blocker_note = "Waiting for credentials"
        attention_task.acceptance_criteria = "Credentials are exercised by a test"
        next_task = Task(
            space_id=space_id,
            project_id=attention_task.project_id,
            solution_id=solution_id,
            task_name="Second assigned task",
            status="to_do",
            priority=4,
            assignee="Worker",
            assignee_user_soeid="WRK123",
        )
        completed_task = Task(
            space_id=space_id,
            project_id=attention_task.project_id,
            solution_id=solution_id,
            task_name="Already complete",
            status="complete",
            priority=1,
            assignee="Worker",
            assignee_user_soeid="wrk123",
        )
        legacy_name_only = Task(
            space_id=space_id,
            project_id=attention_task.project_id,
            solution_id=solution_id,
            task_name="Legacy display-name assignment",
            status="to_do",
            priority=1,
            assignee="Worker",
            assignee_user_soeid=None,
        )
        session.add_all([next_task, completed_task, legacy_name_only])
        session.commit()
        next_task_id = next_task.task_id

    headers = _auth_headers(token, space_id)
    first = await agent_client.get(
        "/project-manager/api/agent/assigned-work",
        headers=headers,
        params={"assignee_user_soeid": "WRK123", "limit": 1},
    )
    assert first.status_code == 200, first.text
    first_body = first.json()
    assert first_body["space_id"] == space_id
    assert first_body["assignee_user_soeid"] == "wrk123"
    assert first_body["has_more"] is True
    assert first_body["next_cursor"]
    assert len(first_body["records"]) == 1
    record = first_body["records"][0]
    assert record["task"]["task_id"] == task_id
    assert record["task"]["acceptance_criteria"] == "Credentials are exercised by a test"
    assert record["task"]["effective_github_repo_url"] == "https://github.com/example/assigned-work"
    assert record["task"]["repo_source"] == "inherited"
    assert record["program_name"] == "Default Program"
    assert record["project_name"] == "Agent Project"
    assert record["solution_name"] == "Agent Solution"
    assert record["needs_attention"] is True
    assert "private_sort_rank" not in record

    second = await agent_client.get(
        "/project-manager/api/agent/assigned-work",
        headers=headers,
        params={
            "assignee_user_soeid": "wrk123",
            "limit": 1,
            "cursor": first_body["next_cursor"],
        },
    )
    assert second.status_code == 200, second.text
    assert [row["task"]["task_id"] for row in second.json()["records"]] == [
        next_task_id
    ]
    assert second.json()["has_more"] is False

    mismatched_cursor = await agent_client.get(
        "/project-manager/api/agent/assigned-work",
        headers=headers,
        params={
            "assignee_user_soeid": "different-user",
            "cursor": first_body["next_cursor"],
        },
    )
    assert mismatched_cursor.status_code == 400
    assert mismatched_cursor.json()["code"] == "INVALID_CURSOR"


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
    assert data["records"][0]["owner"] == "Project Owner"
    assert data["records"][0]["owner_user_soeid"] == "project-owner"
    solution = data["records"][0]["solutions"][0]
    assert solution["solution_id"] == solution_id
    assert solution["tasks"][0]["task_name"] == "Agent Task"

    owner_filter = await agent_client.get(
        "/project-manager/api/agent/work-graph?owner_user_soeid=own123",
        headers=_auth_headers(token, space_id),
    )
    assert owner_filter.status_code == 200, owner_filter.text
    assert owner_filter.json()["records"][0]["project_id"] == project_id

    project_owner_filter = await agent_client.get(
        "/project-manager/api/agent/work-graph?owner_user_soeid=project-owner",
        headers=_auth_headers(token, space_id),
    )
    assert project_owner_filter.status_code == 200, project_owner_filter.text
    assert project_owner_filter.json()["records"][0]["project_id"] == project_id

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
        other_project = (
            session.query(Project).filter(Project.space_id == other_space_id).one()
        )
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
        other_program = (
            session.query(Program).filter(Program.space_id == other_space_id).one()
        )

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
    token, space_id, _other_token, other_space_id, *_ = _seed_work_graph(
        db_sessionmaker
    )
    with db_sessionmaker() as session:
        program = session.query(Program).filter(Program.space_id == space_id).one()
        other_program = (
            session.query(Program).filter(Program.space_id == other_space_id).one()
        )

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
    assert (
        submitted.json()["diff"][0]["fields"]["project_name"]["new"]
        == "Created By Approval"
    )

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
async def test_agent_work_item_details_are_complete_scoped_and_direct(
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
        *_timestamps,
    ) = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        project = session.query(Project).filter(Project.project_id == project_id).one()
        solution = (
            session.query(Solution).filter(Solution.solution_id == solution_id).one()
        )
        task = session.query(Task).filter(Task.task_id == task_id).one()
        program_id = project.program_id
        project.description = "Complete project context"
        project.success_criteria = "Project succeeds"
        project.strategic_objective = "Scale safely"
        solution.github_repo_url = "https://github.com/example/solution"
        solution.description = "Complete solution context"
        solution.problem_statement = "A specific problem"
        solution.risks = "A known risk"
        solution.capacity_hours = 21
        task.done_criteria = "Verified by tests"
        task.estimate_hours = 8
        task.capacity_hours = 5
        session.commit()

    headers = _auth_headers(token, space_id)
    program_response = await agent_client.get(
        f"/project-manager/api/agent/programs/{program_id}", headers=headers
    )
    project_response = await agent_client.get(
        f"/project-manager/api/agent/projects/{project_id}", headers=headers
    )
    solution_response = await agent_client.get(
        f"/project-manager/api/agent/solutions/{solution_id}", headers=headers
    )
    task_response = await agent_client.get(
        f"/project-manager/api/agent/tasks/{task_id}", headers=headers
    )

    for response in (
        program_response,
        project_response,
        solution_response,
        task_response,
    ):
        assert response.status_code == 200, response.text
        assert response.json()["created_at"]
        assert response.json()["updated_at"]

    assert project_response.json()["description"] == "Complete project context"
    assert project_response.json()["success_criteria"] == "Project succeeds"
    assert project_response.json()["strategic_objective"] == "Scale safely"
    assert project_response.json()["owner"] == "Project Owner"
    assert project_response.json()["owner_user_soeid"] == "project-owner"
    assert (
        solution_response.json()["github_repo_url"]
        == "https://github.com/example/solution"
    )
    assert solution_response.json()["problem_statement"] == "A specific problem"
    assert solution_response.json()["capacity_hours"] == 21
    task_data = task_response.json()
    assert task_data["done_criteria"] == "Verified by tests"
    assert task_data["estimate_hours"] == 8
    assert task_data["capacity_hours"] == 5
    assert (
        task_data["effective_github_repo_url"] == "https://github.com/example/solution"
    )
    assert task_data["repo_source"] == "inherited"
    assert isinstance(task_data["urgency_score"], float)

    wrong_space = await agent_client.get(
        f"/project-manager/api/agent/projects/{project_id}",
        headers=_auth_headers(token, other_space_id),
    )
    assert wrong_space.status_code == 403

    missing = await agent_client.get(
        "/project-manager/api/agent/tasks/not-a-task", headers=headers
    )
    assert missing.status_code == 404
    assert missing.json()["code"] == "TASK_NOT_FOUND"


@pytest.mark.anyio
async def test_agent_change_request_can_approve_selected_operations(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="partial-reviewer",
        user_id="partial-reviewer-user",
    )
    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "create only approved projects",
            "idempotency_key": "partial-approval-1",
            "operations": [
                {
                    "client_operation_id": "approved-project",
                    "op": "create",
                    "entity": "project",
                    "fields": {"project_name": "Approved Project"},
                },
                {
                    "client_operation_id": "skipped-project",
                    "op": "create",
                    "entity": "project",
                    "fields": {"project_name": "Skipped Project"},
                },
            ],
        },
    )
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["change_request_id"]

    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/approve-selected-operations",
        headers={"X-Space-Id": space_id},
        json={
            "client_operation_ids": ["approved-project"],
            "review_note": "Only the first project is ready",
        },
    )
    assert approved.status_code == 200, approved.text
    body = approved.json()
    assert body["status"] == "approved"
    assert body["operation_count"] == 2
    assert [
        result["client_operation_id"] for result in body["validation"]["results"]
    ] == ["approved-project"]
    assert [item["client_operation_id"] for item in body["diff"]] == [
        "approved-project",
        "skipped-project",
    ]

    with db_sessionmaker() as session:
        assert (
            session.query(Project)
            .filter(Project.project_name == "Approved Project")
            .one()
        )
        assert (
            session.query(Project)
            .filter(Project.project_name == "Skipped Project")
            .first()
            is None
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
    assert (
        submitted.json()["diff"][0]["fields"]["program_name"]["new"] == "Agent Program"
    )
    with db_sessionmaker() as session:
        assert (
            session.query(Program)
            .filter(Program.program_name == "Agent Program")
            .first()
            is None
        )

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
        program = (
            session.query(Program).filter(Program.program_name == "Agent Program").one()
        )
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
async def test_service_account_can_page_and_get_only_its_change_requests(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    other_token = _seed_additional_agent_token(
        db_sessionmaker,
        space_id=space_id,
        user_id="other-agent",
    )

    async def submit(raw_token: str, index: int):
        return await agent_client.post(
            "/project-manager/api/agent/change-requests",
            headers=_auth_headers(raw_token, space_id),
            json={
                "dry_run": False,
                "reason": f"create project {index}",
                "idempotency_key": f"owned-request-{index}",
                "operations": [
                    {
                        "client_operation_id": f"create-project-{index}",
                        "op": "create",
                        "entity": "project",
                        "fields": {"project_name": f"Owned Project {index}"},
                    }
                ],
            },
        )

    owned = [await submit(token, index) for index in range(3)]
    other = await submit(other_token, 99)
    assert all(response.status_code == 201 for response in [*owned, other])

    missing_space = await agent_client.get(
        "/project-manager/api/agent/change-requests",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert missing_space.status_code == 403
    assert missing_space.json()["code"] == "FORBIDDEN_SPACE"

    first_page = await agent_client.get(
        "/project-manager/api/agent/change-requests?status=all&limit=2",
        headers=_auth_headers(token, space_id),
    )
    assert first_page.status_code == 200, first_page.text
    first_body = first_page.json()
    assert len(first_body["records"]) == 2
    assert first_body["has_more"] is True
    assert first_body["next_cursor"]
    assert first_body["pending_count"] == 3
    assert {row["proposed_by_user_id"] for row in first_body["records"]} == {
        f"user-{space_id}-True-True"
    }

    second_page = await agent_client.get(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        params={
            "status": "all",
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
    )
    assert second_page.status_code == 200, second_page.text
    second_body = second_page.json()
    assert len(second_body["records"]) == 1
    assert second_body["has_more"] is False
    assert second_body["next_cursor"] is None
    paged_ids = {
        row["change_request_id"]
        for row in [*first_body["records"], *second_body["records"]]
    }
    assert paged_ids == {response.json()["change_request_id"] for response in owned}

    filtered = await agent_client.get(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        params={"status": "all", "idempotency_key": "owned-request-1"},
    )
    assert filtered.status_code == 200, filtered.text
    assert [row["idempotency_key"] for row in filtered.json()["records"]] == [
        "owned-request-1"
    ]

    own_detail = await agent_client.get(
        (
            "/project-manager/api/agent/change-requests/"
            f"{owned[0].json()['change_request_id']}"
        ),
        headers=_auth_headers(token, space_id),
    )
    assert own_detail.status_code == 200, own_detail.text

    other_detail = await agent_client.get(
        (
            "/project-manager/api/agent/change-requests/"
            f"{other.json()['change_request_id']}"
        ),
        headers=_auth_headers(token, space_id),
    )
    assert other_detail.status_code == 404

    changed_filter_cursor = await agent_client.get(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        params={
            "status": "pending",
            "limit": 2,
            "cursor": first_body["next_cursor"],
        },
    )
    assert changed_filter_cursor.status_code == 400
    assert changed_filter_cursor.json()["code"] == "INVALID_CURSOR"

    reviewer_soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="queue-reviewer",
        user_id="queue-reviewer-user",
    )
    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": reviewer_soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    reviewer_queue = await agent_client.get(
        "/project-manager/api/agent/change-requests?status=all",
        headers={"X-Space-Id": space_id},
    )
    assert reviewer_queue.status_code == 200, reviewer_queue.text
    assert reviewer_queue.json()["pending_count"] == 4
    assert len(reviewer_queue.json()["records"]) == 4


@pytest.mark.anyio
async def test_service_account_can_cancel_only_its_pending_request_and_replace_it(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    other_token = _seed_additional_agent_token(
        db_sessionmaker,
        space_id=space_id,
        user_id="cancel-other-agent",
    )
    original_payload = {
        "dry_run": False,
        "reason": "create original project",
        "idempotency_key": "cancel-original",
        "operations": [
            {
                "client_operation_id": "create-original",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Original Cancel Project"},
            }
        ],
    }
    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=original_payload,
    )
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["change_request_id"]

    other_cancel = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/cancel",
        headers=_auth_headers(other_token, space_id),
    )
    assert other_cancel.status_code == 404
    assert other_cancel.json()["code"] == "CHANGE_REQUEST_NOT_FOUND"

    cancelled = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/cancel",
        headers=_auth_headers(token, space_id),
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    repeated_cancel = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/cancel",
        headers=_auth_headers(token, space_id),
    )
    assert repeated_cancel.status_code == 200, repeated_cancel.text
    assert repeated_cancel.json()["status"] == "cancelled"

    cancelled_list = await agent_client.get(
        "/project-manager/api/agent/change-requests?status=cancelled",
        headers=_auth_headers(token, space_id),
    )
    assert cancelled_list.status_code == 200, cancelled_list.text
    assert [row["change_request_id"] for row in cancelled_list.json()["records"]] == [
        request_id
    ]

    idempotent_retry = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=original_payload,
    )
    assert idempotent_retry.status_code == 201, idempotent_retry.text
    assert idempotent_retry.json()["change_request_id"] == request_id
    assert idempotent_retry.json()["status"] == "cancelled"

    replacement_payload = {
        **original_payload,
        "reason": "replace cancelled project request",
        "idempotency_key": "cancel-replacement",
        "operations": [
            {
                "client_operation_id": "create-replacement",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Replacement Cancel Project"},
            }
        ],
    }
    replacement = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=replacement_payload,
    )
    assert replacement.status_code == 201, replacement.text
    assert replacement.json()["status"] == "pending"
    assert replacement.json()["change_request_id"] != request_id

    with db_sessionmaker() as session:
        audit_rows = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "agent_change_request")
            .filter(ChangeLog.entity_id == request_id)
            .filter(ChangeLog.action == "cancel")
            .all()
        )
        assert len(audit_rows) == 1
        assert audit_rows[0].old_value == "pending"
        assert audit_rows[0].new_value == "cancelled"


@pytest.mark.anyio
async def test_service_account_can_update_its_pending_request_in_place(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    other_token = _seed_additional_agent_token(
        db_sessionmaker,
        space_id=space_id,
        user_id="update-other-agent",
    )
    original = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "create the original project",
            "idempotency_key": "update-in-place",
            "operations": [
                {
                    "client_operation_id": "create-project",
                    "op": "create",
                    "entity": "project",
                    "fields": {"project_name": "Original Project"},
                }
            ],
        },
    )
    assert original.status_code == 201, original.text
    original_value = original.json()
    request_id = original_value["change_request_id"]
    replacement_body = {
        "if_request_updated_at": original_value["updated_at"],
        "reason": "create the corrected project",
        "operations": [
            {
                "client_operation_id": "create-project",
                "op": "create",
                "entity": "project",
                "fields": {"project_name": "Corrected Project"},
            }
        ],
    }

    hidden = await agent_client.put(
        f"/project-manager/api/agent/change-requests/{request_id}",
        headers=_auth_headers(other_token, space_id),
        json=replacement_body,
    )
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "CHANGE_REQUEST_NOT_FOUND"

    updated = await agent_client.put(
        f"/project-manager/api/agent/change-requests/{request_id}",
        headers=_auth_headers(token, space_id),
        json=replacement_body,
    )
    assert updated.status_code == 200, updated.text
    updated_value = updated.json()
    assert updated_value["change_request_id"] == request_id
    assert updated_value["idempotency_key"] == "update-in-place"
    assert updated_value["reason"] == "create the corrected project"
    assert updated_value["operations"][0]["fields"]["project_name"] == "Corrected Project"
    assert updated_value["diff"][0]["fields"]["project_name"]["new"] == "Corrected Project"

    stale = await agent_client.put(
        f"/project-manager/api/agent/change-requests/{request_id}",
        headers=_auth_headers(token, space_id),
        json=replacement_body,
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "CHANGE_REQUEST_CHANGED"

    with db_sessionmaker() as session:
        assert session.query(AgentChangeRequest).count() == 1
        replacement_audit = (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "agent_change_request")
            .filter(ChangeLog.entity_id == request_id)
            .filter(ChangeLog.action == "update")
            .filter(ChangeLog.field == "proposal")
            .one()
        )
        assert replacement_audit.old_value == "previous"
        assert replacement_audit.new_value == "replaced"

    cancelled = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/cancel",
        headers=_auth_headers(token, space_id),
    )
    assert cancelled.status_code == 200, cancelled.text
    terminal_update = await agent_client.put(
        f"/project-manager/api/agent/change-requests/{request_id}",
        headers=_auth_headers(token, space_id),
        json={
            **replacement_body,
            "if_request_updated_at": cancelled.json()["updated_at"],
        },
    )
    assert terminal_update.status_code == 409
    assert terminal_update.json()["code"] == "CHANGE_REQUEST_NOT_PENDING"


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


@pytest.mark.anyio
async def test_agent_work_search_is_typed_filtered_paginated_and_cursor_bound(
    agent_client, db_sessionmaker
):
    seeded = _seed_work_graph(db_sessionmaker)
    token, space_id = seeded[0], seeded[1]
    project_id, solution_id = seeded[4], seeded[5]
    with db_sessionmaker() as session:
        for index in range(5):
            session.add(
                Task(
                    space_id=space_id,
                    project_id=project_id,
                    solution_id=solution_id,
                    task_name=f"Searchable Task {index}",
                    status="in_progress" if index % 2 else "to_do",
                    priority=index + 1,
                    assignee=f"Worker {index}",
                    assignee_user_soeid="shared-worker"
                    if index < 3
                    else f"worker-{index}",
                )
            )
        session.commit()

    headers = _auth_headers(token, space_id)
    cursor = None
    first_cursor = None
    seen: list[str] = []
    while True:
        params = {
            "entity_type": "task",
            "parent_id": solution_id,
            "q": "Searchable",
            "limit": 2,
        }
        if cursor:
            params["cursor"] = cursor
        response = await agent_client.get(
            "/project-manager/api/agent/work-items", headers=headers, params=params
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["entity_type"] == "task"
        seen.extend(record["entity_id"] for record in body["records"])
        cursor = body["next_cursor"]
        first_cursor = first_cursor or cursor
        if not body["has_more"]:
            break
    assert len(seen) == 5
    assert len(set(seen)) == 5

    principal = await agent_client.get(
        "/project-manager/api/agent/work-items",
        headers=headers,
        params={
            "entity_type": "task",
            "principal_soeid": "shared-worker",
            "limit": 10,
        },
    )
    assert principal.status_code == 200, principal.text
    assert len(principal.json()["records"]) == 3
    assert all(
        row["assignee_user_soeid"] == "shared-worker"
        for row in principal.json()["records"]
    )

    changed_filter = await agent_client.get(
        "/project-manager/api/agent/work-items",
        headers=headers,
        params={"entity_type": "task", "q": "different", "cursor": first_cursor},
    )
    assert changed_filter.status_code == 400

    invalid_type = await agent_client.get(
        "/project-manager/api/agent/work-items",
        headers=headers,
        params={"entity_type": "everything"},
    )
    assert invalid_type.status_code == 400
    assert invalid_type.json()["code"] == "INVALID_ENTITY_TYPE"


@pytest.mark.anyio
async def test_agent_work_graph_is_cursor_paginated_task_filterable_and_projectable(
    agent_client, db_sessionmaker
):
    seeded = _seed_work_graph(db_sessionmaker)
    token, space_id = seeded[0], seeded[1]
    first_project_id, first_solution_id, first_task_id = seeded[4:7]
    with db_sessionmaker() as session:
        first_project = (
            session.query(Project).filter(Project.project_id == first_project_id).one()
        )
        first_solution = (
            session.query(Solution)
            .filter(Solution.solution_id == first_solution_id)
            .one()
        )
        first_task = session.query(Task).filter(Task.task_id == first_task_id).one()
        first_project.description = "Full project detail"
        first_solution.problem_statement = "Full solution detail"
        first_task.done_criteria = "Full task detail"
        for index in range(4):
            session.add(
                Project(
                    space_id=space_id,
                    program_id=first_project.program_id,
                    project_name=f"Graph Page Project {index}",
                    status="active",
                    sponsor="Sponsor",
                )
            )
        session.commit()

    headers = _auth_headers(token, space_id)
    cursor = None
    first_cursor = None
    seen: list[str] = []
    while True:
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        response = await agent_client.get(
            "/project-manager/api/agent/work-graph", headers=headers, params=params
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["projection"] == "summary"
        assert body["filter_semantics"] == "parent_match_full_children"
        seen.extend(row["project_id"] for row in body["records"])
        cursor = body.get("next_cursor")
        first_cursor = first_cursor or cursor
        if not body["has_more"]:
            break
    assert len(seen) == 5
    assert len(set(seen)) == 5

    task_filtered = await agent_client.get(
        "/project-manager/api/agent/work-graph",
        headers=headers,
        params={"task_id": first_task_id, "projection": "full"},
    )
    assert task_filtered.status_code == 200, task_filtered.text
    full = task_filtered.json()
    assert [row["project_id"] for row in full["records"]] == [first_project_id]
    assert full["records"][0]["description"] == "Full project detail"
    assert (
        full["records"][0]["solutions"][0]["problem_statement"]
        == "Full solution detail"
    )
    assert (
        full["records"][0]["solutions"][0]["tasks"][0]["done_criteria"]
        == "Full task detail"
    )

    mismatched_cursor = await agent_client.get(
        "/project-manager/api/agent/work-graph",
        headers=headers,
        params={"cursor": first_cursor, "projection": "full"},
    )
    assert mismatched_cursor.status_code == 400
    assert mismatched_cursor.json()["code"] == "INVALID_CURSOR"


@pytest.mark.anyio
async def test_agent_patch_client_refs_create_hierarchy_atomically(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="hierarchy-reviewer",
        user_id="hierarchy-reviewer-user",
    )
    payload = {
        "dry_run": False,
        "reason": "Create one coherent work hierarchy",
        "idempotency_key": "hierarchy-with-refs-1",
        "operations": [
            {
                "client_operation_id": "program",
                "op": "create",
                "entity": "program",
                "ref": "new-program",
                "fields": {"program_name": "Reference Program"},
            },
            {
                "client_operation_id": "project",
                "op": "create",
                "entity": "project",
                "ref": "new-project",
                "program_ref": "new-program",
                "fields": {"project_name": "Reference Project"},
            },
            {
                "client_operation_id": "solution",
                "op": "create",
                "entity": "solution",
                "ref": "new-solution",
                "project_ref": "new-project",
                "fields": {"solution_name": "Reference Solution"},
            },
            {
                "client_operation_id": "task",
                "op": "create",
                "entity": "task",
                "ref": "new-task",
                "solution_ref": "new-solution",
                "fields": {"task_name": "Reference Task"},
            },
        ],
    }
    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json=payload,
    )
    assert submitted.status_code == 201, submitted.text
    body = submitted.json()
    assert body["validation"]["valid"] is True
    assert [item["entity_ref"] for item in body["diff"]] == [
        "new-program",
        "new-project",
        "new-solution",
        "new-task",
    ]

    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{body['change_request_id']}/approve",
        headers={"X-Space-Id": space_id},
        json={"review_note": "Hierarchy reviewed"},
    )
    assert approved.status_code == 200, approved.text
    result_rows = approved.json()["validation"]["results"]
    assert all(row["applied"] for row in result_rows)
    assert all(row["entity_id"] for row in result_rows)
    assert [row["ref"] for row in result_rows] == [
        "new-program",
        "new-project",
        "new-solution",
        "new-task",
    ]
    with db_sessionmaker() as session:
        program = (
            session.query(Program)
            .filter(Program.program_name == "Reference Program")
            .one()
        )
        project = (
            session.query(Project)
            .filter(Project.project_name == "Reference Project")
            .one()
        )
        solution = (
            session.query(Solution)
            .filter(Solution.solution_name == "Reference Solution")
            .one()
        )
        task = session.query(Task).filter(Task.task_name == "Reference Task").one()
        assert project.program_id == program.program_id
        assert solution.project_id == project.project_id
        assert task.solution_id == solution.solution_id
        assert task.project_id == project.project_id

    invalid = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers=_auth_headers(token, space_id),
        json={
            "operations": [
                {
                    "client_operation_id": "forward",
                    "op": "create",
                    "entity": "solution",
                    "project_ref": "later-project",
                    "fields": {"solution_name": "Invalid"},
                },
                {
                    "client_operation_id": "later",
                    "op": "create",
                    "entity": "project",
                    "ref": "later-project",
                    "fields": {"project_name": "Later"},
                },
            ]
        },
    )
    assert invalid.status_code == 200, invalid.text
    assert invalid.json()["valid"] is False
    assert invalid.json()["results"][0]["code"] == "REFERENCE_NOT_FOUND_OR_FORWARD"


@pytest.mark.anyio
async def test_agent_archive_is_approval_gated_scoped_and_explicit_about_descendants(
    agent_client, db_sessionmaker
):
    seeded = _seed_work_graph(db_sessionmaker)
    token, space_id = seeded[0], seeded[1]
    project_id, solution_id, task_id = seeded[4:7]
    solution_updated_at = seeded[8]
    soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="archive-reviewer",
        user_id="archive-reviewer-user",
    )
    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(token, space_id),
        json={
            "dry_run": False,
            "reason": "Archive an obsolete solution",
            "idempotency_key": "archive-solution-1",
            "operations": [
                {
                    "client_operation_id": "archive-solution",
                    "op": "archive",
                    "entity": "solution",
                    "id": solution_id,
                    "if_updated_at": solution_updated_at,
                }
            ],
        },
    )
    assert submitted.status_code == 201, submitted.text
    diff = submitted.json()["diff"][0]["fields"]
    assert diff["lifecycle"] == {"old": "active", "new": "archived"}
    assert diff["descendant_visibility"]["new"] == "inaccessible_with_parent"

    login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": soeid, "password": "Password123"},
    )
    assert login.status_code == 200, login.text
    approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{submitted.json()['change_request_id']}/approve",
        headers={"X-Space-Id": space_id},
        json={"review_note": "Archive confirmed"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    headers = _auth_headers(token, space_id)
    solution_detail = await agent_client.get(
        f"/project-manager/api/agent/solutions/{solution_id}", headers=headers
    )
    task_detail = await agent_client.get(
        f"/project-manager/api/agent/tasks/{task_id}", headers=headers
    )
    assert solution_detail.status_code == 404
    assert task_detail.status_code == 404
    archived_search = await agent_client.get(
        "/project-manager/api/agent/work-items",
        headers=headers,
        params={
            "entity_type": "solution",
            "entity_id": solution_id,
            "lifecycle": "archived",
        },
    )
    assert archived_search.status_code == 200, archived_search.text
    assert archived_search.json()["records"][0]["lifecycle"] == "archived"
    hidden_child_search = await agent_client.get(
        "/project-manager/api/agent/work-items",
        headers=headers,
        params={"entity_type": "task", "entity_id": task_id},
    )
    assert hidden_child_search.status_code == 200, hidden_child_search.text
    assert hidden_child_search.json()["records"] == []
    with db_sessionmaker() as session:
        archived_solution = (
            session.query(Solution).filter(Solution.solution_id == solution_id).one()
        )
        child_task = session.query(Task).filter(Task.task_id == task_id).one()
        assert archived_solution.deleted_at is not None
        assert child_task.deleted_at is None
        assert (
            session.query(ChangeLog)
            .filter(ChangeLog.entity_type == "solution")
            .filter(ChangeLog.entity_id == solution_id)
            .filter(ChangeLog.action == "delete")
            .count()
            > 0
        )

    with db_sessionmaker() as session:
        project = session.query(Project).filter(Project.project_id == project_id).one()
        program = (
            session.query(Program)
            .filter(Program.program_id == project.program_id)
            .one()
        )
        program_id = program.program_id
        program_updated_at = program.updated_at.isoformat()
        project_updated_at = project.updated_at.isoformat()
        current_description = project.description
    validation = await agent_client.post(
        "/project-manager/api/agent/patches/validate",
        headers=headers,
        json={
            "operations": [
                {
                    "client_operation_id": "program-with-child",
                    "op": "archive",
                    "entity": "program",
                    "id": program_id,
                    "if_updated_at": program_updated_at,
                },
                {
                    "client_operation_id": "noop-project",
                    "op": "update",
                    "entity": "project",
                    "id": project_id,
                    "if_updated_at": project_updated_at,
                    "fields": {"description": current_description},
                },
            ]
        },
    )
    assert validation.status_code == 200, validation.text
    assert [row["code"] for row in validation.json()["results"]] == [
        "ACTIVE_CHILDREN",
        "NO_CHANGES",
    ]


@pytest.mark.anyio
async def test_human_delegated_review_requires_session_token_and_exact_request_version(
    agent_client, db_sessionmaker
):
    service_token, space_id = _seed_agent_token(db_sessionmaker)
    human_soeid, _ = _seed_cookie_user(
        db_sessionmaker,
        space_id=space_id,
        soeid="delegated-human",
        user_id="delegated-human",
    )
    human_login = await agent_client.post(
        "/project-manager/api/auth/login",
        json={"soeid": human_soeid, "password": "Password123"},
    )
    assert human_login.status_code == 200, human_login.text
    delegated_session = await agent_client.post(
        "/project-manager/api/agent/delegated-session"
    )
    assert delegated_session.status_code == 200, delegated_session.text
    assert delegated_session.json()["expires_in_seconds"] == 600
    human_token = delegated_session.json()["access_token"]
    submitted = await agent_client.post(
        "/project-manager/api/agent/change-requests",
        headers=_auth_headers(service_token, space_id),
        json={
            "dry_run": False,
            "reason": "Delegated human review",
            "idempotency_key": "delegated-review-1",
            "operations": [
                {
                    "client_operation_id": "create-delegated-project",
                    "op": "create",
                    "entity": "project",
                    "fields": {"project_name": "Delegated Project"},
                }
            ],
        },
    )
    assert submitted.status_code == 201, submitted.text
    request_id = submitted.json()["change_request_id"]

    human_headers = _auth_headers(human_token, space_id)
    reviewed = await agent_client.get(
        f"/project-manager/api/agent/change-requests/{request_id}/delegated-review",
        headers=human_headers,
    )
    assert reviewed.status_code == 200, reviewed.text
    observed_at = reviewed.json()["updated_at"]

    service_attempt = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/delegated-approve",
        headers=_auth_headers(service_token, space_id),
        json={
            "confirm_change_request_id": request_id,
            "if_request_updated_at": observed_at,
        },
    )
    assert service_attempt.status_code == 403
    assert service_attempt.json()["code"] == "HUMAN_DELEGATED_TOKEN_REQUIRED"

    mismatch = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/delegated-approve",
        headers=human_headers,
        json={
            "confirm_change_request_id": "different-request",
            "if_request_updated_at": observed_at,
        },
    )
    assert mismatch.status_code == 409
    assert mismatch.json()["code"] == "CONFIRMATION_REQUEST_MISMATCH"

    approved = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/delegated-approve",
        headers=human_headers,
        json={
            "confirm_change_request_id": request_id,
            "if_request_updated_at": observed_at,
            "review_note": "Explicit delegated confirmation",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by_user_id"] == "delegated-human"
    with db_sessionmaker() as session:
        assert (
            session.query(Project)
            .filter(Project.project_name == "Delegated Project")
            .one()
        )

    replay = await agent_client.post(
        f"/project-manager/api/agent/change-requests/{request_id}/delegated-approve",
        headers=human_headers,
        json={
            "confirm_change_request_id": request_id,
            "if_request_updated_at": observed_at,
        },
    )
    assert replay.status_code == 409


@pytest.mark.anyio
async def test_agent_audit_feed_reference_data_and_filtered_openapi_are_machine_usable(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    with db_sessionmaker() as session:
        session.add(
            Space(
                space_id="not-accessible", name="Not Accessible", slug="not-accessible"
            )
        )
        session.flush()
        for index in range(5):
            session.add(
                ChangeLog(
                    change_id=f"audit-{index}",
                    entity_type="task",
                    entity_id=f"task-{index}",
                    action="update",
                    field="status",
                    old_value="to_do",
                    new_value="in_progress",
                    user_id="audit-user",
                    space_id=space_id,
                    request_id="audit-request",
                )
            )
        session.add(
            ChangeLog(
                change_id="other-space-audit",
                entity_type="task",
                entity_id="other-task",
                action="update",
                user_id="other-user",
                space_id="not-accessible",
            )
        )
        session.commit()

    headers = _auth_headers(token, space_id)
    cursor = None
    first_cursor = None
    seen: list[str] = []
    while True:
        params = {"entity_type": "task", "request_id": "audit-request", "limit": 2}
        if cursor:
            params["cursor"] = cursor
        response = await agent_client.get(
            "/project-manager/api/agent/audit-feed", headers=headers, params=params
        )
        assert response.status_code == 200, response.text
        body = response.json()
        seen.extend(row["change_id"] for row in body["records"])
        cursor = body.get("next_cursor")
        first_cursor = first_cursor or cursor
        if not body["has_more"]:
            break
    assert len(seen) == 5
    assert len(set(seen)) == 5
    assert "other-space-audit" not in seen

    cursor_mismatch = await agent_client.get(
        "/project-manager/api/agent/audit-feed",
        headers=headers,
        params={"entity_type": "project", "cursor": first_cursor},
    )
    assert cursor_mismatch.status_code == 400
    assert cursor_mismatch.json()["code"] == "INVALID_CURSOR"

    reference = await agent_client.get(
        "/project-manager/api/agent/reference-data",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert reference.status_code == 200, reference.text
    assert reference.headers["etag"] == '"agent-reference-1.1"'
    reference_data = reference.json()
    assert reference_data["operations"] == ["archive", "create", "update"]
    assert "project_id" not in reference_data["fields"]["solution"]["create"]
    assert "project_id" in reference_data["fields"]["solution"]["update"]
    assert reference_data["statuses"]["task"] == [
        "to_do",
        "in_progress",
        "on_hold",
        "complete",
        "abandoned",
    ]
    assert reference_data["limits"]["patch_operations"] == 25
    assert reference_data["filters"]["assigned_work"] == [
        "assignee_user_soeid",
        "cursor",
        "limit",
    ]

    openapi = await agent_client.get(
        "/project-manager/api/agent/openapi.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert openapi.status_code == 200, openapi.text
    contract = openapi.json()
    assert contract["paths"]
    assert "/project-manager/api/agent/assigned-work" in contract["paths"]
    assert all("/api/agent/" in path for path in contract["paths"])
    assert not any(path.endswith("/api/projects") for path in contract["paths"])
    detail_operation = contract["paths"][
        "/project-manager/api/agent/projects/{project_id}"
    ]["get"]
    assert detail_operation["x-agent-safe"] is True
    assert any(
        parameter["name"] == "X-Space-Id" and parameter["required"] is True
        for parameter in detail_operation["parameters"]
    )


@pytest.mark.anyio
async def test_agent_people_and_teams_are_scoped_paginated_and_capacity_aware(
    agent_client, db_sessionmaker
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    with db_sessionmaker() as session:
        for index in range(5):
            user = User(
                user_id=f"person-{index}",
                soeid=f"person{index}",
                email=f"person{index}@example.com",
                display_name=f"Person {index}",
                password_hash=hash_password("Password123"),
                role="user",
                is_active=True,
                team_tag="delivery",
                capacity_hours=30 + index,
                capacity_fte_month=0.8,
            )
            session.add(user)
            session.flush()
            session.add(
                SpaceMembership(
                    space_id=space_id,
                    user_id=user.user_id,
                    role="space_admin" if index == 0 else "member",
                    status="active",
                )
            )
        for index in range(3):
            team = Team(
                space_id=space_id,
                name=f"Delivery Team {index}",
                description="Scoped delivery team",
                lead=f"person{index}",
                default_capacity_per_week=40,
                default_capacity_fte_month=1.0,
                capacity_unit="hours",
            )
            session.add(team)
            session.flush()
            for member_index in range(3):
                session.add(
                    TeamMember(
                        space_id=space_id,
                        team_id=team.team_id,
                        member_name=f"Member {member_index}",
                        role="lead" if member_index == 0 else "member",
                        hours_capacity=35 + member_index,
                        capacity_fte_month=0.9,
                    )
                )
        session.commit()

    headers = _auth_headers(token, space_id)
    cursor = None
    people_ids: list[str] = []
    while True:
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        response = await agent_client.get(
            "/project-manager/api/agent/people", headers=headers, params=params
        )
        assert response.status_code == 200, response.text
        body = response.json()
        people_ids.extend(row["user_id"] for row in body["records"])
        cursor = body.get("next_cursor")
        if not body["has_more"]:
            break
    assert len(people_ids) == 6
    assert len(set(people_ids)) == 6

    exact_person = await agent_client.get(
        "/project-manager/api/agent/people",
        headers=headers,
        params={"soeid": "person0"},
    )
    assert exact_person.status_code == 200, exact_person.text
    assert exact_person.json()["records"][0]["membership_role"] == "space_admin"
    assert exact_person.json()["records"][0]["capacity_hours"] == 30

    teams = await agent_client.get(
        "/project-manager/api/agent/teams",
        headers=headers,
        params={"limit": 2},
    )
    assert teams.status_code == 200, teams.text
    assert teams.json()["has_more"] is True
    first_team = teams.json()["records"][0]
    assert first_team["member_count"] == 3
    assert first_team["default_capacity_per_week"] == 40

    members = await agent_client.get(
        f"/project-manager/api/agent/teams/{first_team['team_id']}/members",
        headers=headers,
        params={"limit": 2},
    )
    assert members.status_code == 200, members.text
    assert members.json()["has_more"] is True
    assert members.json()["records"][0]["role"] == "lead"
    assert members.json()["records"][0]["hours_capacity"] == 35
