from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.models import Phase, Subcomponent
from backend.main import app as fastapi_app
from backend.app import deps as deps_module
from backend.app.services.smart_cache import clear_cache
from backend.app.services.spaces import SpaceContext


def seed_phases(SessionLocal):
    with SessionLocal() as session:
        session.add_all(
            [
                Phase(
                    phase_id="backlog",
                    phase_group="Backlog",
                    phase_name="Backlog",
                    sequence=1,
                ),
                Phase(
                    phase_id="requirements",
                    phase_group="Planning",
                    phase_name="Requirements",
                    sequence=2,
                ),
            ]
        )
        session.commit()


async def create_project_solution(client):
    project = (
        await client.post(
        "/project-manager/api/projects/",
        json={
            "project_name": "Data Platform",
            "description": "Modernize data stack",
            "sponsor": "CFO Office",
        },
        )
    ).json()
    solution = (
        await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={"solution_name": "Access Controls", "version": "0.1.0", "owner": "Solution Owner"},
        )
    ).json()
    return project, solution


async def enable_phases(client, solution_id: str):
    resp = await client.post(
        f"/project-manager/api/solutions/{solution_id}/phases",
        json={
            "phases": [
                {"phase_id": "backlog", "is_enabled": True},
                {"phase_id": "requirements", "is_enabled": True},
            ]
        },
    )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_create_and_list_subcomponents(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Define RBAC roles",
            "priority": 1,
            "due_date": date.today().isoformat(),
            "assignee": "Engineer A",
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["subcomponent_name"] == "Define RBAC roles"
    assert data["priority"] == 1
    assert data["assignee"] == "Engineer A"

    list_resp = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) == 1
    assert items[0]["assignee"] == "Engineer A"


@pytest.mark.anyio
async def test_create_subcomponent_defaults_assignee_and_priority(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={"subcomponent_name": "Minimal Subcomponent"},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["subcomponent_name"] == "Minimal Subcomponent"
    assert data["status"] == "to_do"
    assert data["priority"] == 3
    assert data["blocked"] is False
    assert data["assignee"] == "Test User"
    assert data["assignee_user_soeid"] == "tu12345"


@pytest.mark.anyio
async def test_subcomponent_crud_normalizes_names_and_clears_stale_blocker_note(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    blank_create = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={"subcomponent_name": "  "},
    )
    assert blank_create.status_code == 400, blank_create.text
    assert blank_create.json()["detail"] == "subcomponent_name is required"

    create = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "  Trimmed Task  ",
            "blocked": True,
            "blocker_note": "Waiting on access",
        },
    )
    assert create.status_code == 201, create.text
    subcomponent = create.json()
    assert subcomponent["subcomponent_name"] == "Trimmed Task"
    assert subcomponent["blocked"] is True
    assert subcomponent["blocker_note"] == "Waiting on access"

    blank_update = await client.patch(
        f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}",
        json={"subcomponent_name": "\t"},
    )
    assert blank_update.status_code == 400, blank_update.text
    assert blank_update.json()["detail"] == "subcomponent_name is required"

    unblocked = await client.patch(
        f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}",
        json={"blocked": False},
    )
    assert unblocked.status_code == 200, unblocked.text
    assert unblocked.json()["blocked"] is False
    assert unblocked.json()["blocker_note"] is None


@pytest.mark.anyio
async def test_subcomponent_repo_override_inherits_overrides_and_clears(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    project, _ = await create_project_solution(client)
    solution_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Repo Anchored Solution",
            "version": "1.0.0",
            "owner": "Solution Owner",
            "github_repo_url": "https://github.com/example-org/platform-service.git/",
        },
    )
    assert solution_resp.status_code == 201, solution_resp.text
    solution = solution_resp.json()

    create_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={"subcomponent_name": "Inherited Task"},
    )
    assert create_resp.status_code == 201, create_resp.text
    created = create_resp.json()
    assert created["github_repo_url"] is None
    assert created["effective_github_repo_url"] == "https://github.com/example-org/platform-service"
    assert created["repo_source"] == "inherited"

    update_resp = await client.patch(
        f"/project-manager/api/subcomponents/{created['subcomponent_id']}",
        json={"github_repo_url": "https://github.com/example-org/frontend-app"},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["github_repo_url"] == "https://github.com/example-org/frontend-app"
    assert updated["effective_github_repo_url"] == "https://github.com/example-org/frontend-app"
    assert updated["repo_source"] == "override"

    clear_resp = await client.patch(
        f"/project-manager/api/subcomponents/{created['subcomponent_id']}",
        json={"github_repo_url": ""},
    )
    assert clear_resp.status_code == 200, clear_resp.text
    cleared = clear_resp.json()
    assert cleared["github_repo_url"] is None
    assert cleared["effective_github_repo_url"] == "https://github.com/example-org/platform-service"
    assert cleared["repo_source"] == "inherited"


@pytest.mark.anyio
async def test_solution_repo_update_refreshes_cached_subcomponent_repo_inheritance(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    clear_cache()
    try:
        project, _ = await create_project_solution(client)
        solution_resp = await client.post(
            f"/project-manager/api/projects/{project['project_id']}/solutions",
            json={
                "solution_name": "Repo Inheritance Solution",
                "version": "1.0.0",
                "owner": "Solution Owner",
                "github_repo_url": "https://github.com/example-org/platform-service",
            },
        )
        assert solution_resp.status_code == 201, solution_resp.text
        solution = solution_resp.json()

        create_resp = await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Inherited Task"},
        )
        assert create_resp.status_code == 201, create_resp.text
        subcomponent = create_resp.json()

        primed_list = await client.get("/project-manager/api/subcomponents")
        assert primed_list.status_code == 200, primed_list.text
        assert primed_list.json()[0]["effective_github_repo_url"] == "https://github.com/example-org/platform-service"

        primed_solution_list = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents"
        )
        assert primed_solution_list.status_code == 200, primed_solution_list.text
        assert primed_solution_list.json()[0]["effective_github_repo_url"] == "https://github.com/example-org/platform-service"

        primed_detail = await client.get(
            f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}"
        )
        assert primed_detail.status_code == 200, primed_detail.text
        assert primed_detail.json()["effective_github_repo_url"] == "https://github.com/example-org/platform-service"

        update_resp = await client.patch(
            f"/project-manager/api/solutions/{solution['solution_id']}",
            json={"github_repo_url": "https://github.com/example-org/platform-service-v2"},
        )
        assert update_resp.status_code == 200, update_resp.text

        list_resp = await client.get("/project-manager/api/subcomponents")
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json()[0]["effective_github_repo_url"] == "https://github.com/example-org/platform-service-v2"

        solution_list_resp = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents"
        )
        assert solution_list_resp.status_code == 200, solution_list_resp.text
        assert solution_list_resp.json()[0]["effective_github_repo_url"] == "https://github.com/example-org/platform-service-v2"

        detail_resp = await client.get(
            f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}"
        )
        assert detail_resp.status_code == 200, detail_resp.text
        assert detail_resp.json()["effective_github_repo_url"] == "https://github.com/example-org/platform-service-v2"
        assert detail_resp.json()["repo_source"] == "inherited"
    finally:
        clear_cache()


@pytest.mark.anyio
async def test_subcomponent_rejects_invalid_github_repo_override(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Bad Repo Task",
            "github_repo_url": "https://github.com/example-org/platform-service/pull/1",
        },
    )
    assert resp.status_code == 400, resp.text
    assert "github_repo_url" in resp.json()["detail"]


@pytest.mark.anyio
async def test_list_all_subcomponents_filter_by_assignee(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    assert (
        (await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Task A", "assignee": "Engineer A"},
        )).status_code
        == 201
    )
    assert (
        (await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Task B", "assignee": "Engineer B"},
        )).status_code
        == 201
    )

    all_resp = await client.get("/project-manager/api/subcomponents")
    assert all_resp.status_code == 200
    assert len(all_resp.json()) == 2

    filtered = await client.get("/project-manager/api/subcomponents", params={"assignee": "Engineer A"})
    assert filtered.status_code == 200
    items = filtered.json()
    assert len(items) == 1
    assert items[0]["subcomponent_name"] == "Task A"


@pytest.mark.anyio
async def test_list_subcomponents_includes_actionability_metadata(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)
    today = date.today()

    create_payloads = [
        {
            "subcomponent_name": "Overdue Task",
            "status": "to_do",
            "priority": 1,
            "due_date": (today - timedelta(days=1)).isoformat(),
            "assignee": "Engineer A",
        },
        {
            "subcomponent_name": "Due Soon Task",
            "status": "in_progress",
            "priority": 2,
            "due_date": (today + timedelta(days=3)).isoformat(),
            "assignee": "Engineer B",
        },
        {
            "subcomponent_name": "Stale Task",
            "status": "to_do",
            "priority": 4,
            "due_date": (today + timedelta(days=30)).isoformat(),
            "assignee": "Engineer C",
        },
    ]
    for payload in create_payloads:
        resp = await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json=payload,
        )
        assert resp.status_code == 201, resp.text

    with db_sessionmaker() as session:
        stale = (
            session.query(Subcomponent)
            .filter(Subcomponent.subcomponent_name == "Stale Task")
            .first()
        )
        assert stale is not None
        stale.updated_at = (datetime.now(timezone.utc) - timedelta(days=10)).replace(
            tzinfo=None
        )
        session.add(stale)
        session.commit()

    list_resp = await client.get("/project-manager/api/subcomponents")
    assert list_resp.status_code == 200, list_resp.text
    rows = {item["subcomponent_name"]: item for item in list_resp.json()}

    overdue = rows["Overdue Task"]
    due_soon = rows["Due Soon Task"]
    stale = rows["Stale Task"]

    assert overdue["is_overdue"] is True
    assert due_soon["is_due_soon"] is True
    assert stale["is_stale"] is True
    assert overdue["urgency_score"] > stale["urgency_score"]


@pytest.mark.anyio
async def test_batch_update_subcomponents(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    first_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Batch Task A",
            "status": "to_do",
            "priority": 3,
            "due_date": date.today().isoformat(),
            "assignee": "Engineer A",
        },
    )
    assert first_resp.status_code == 201, first_resp.text
    first = first_resp.json()
    second_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Batch Task B",
            "status": "to_do",
            "priority": 4,
            "due_date": (date.today() + timedelta(days=2)).isoformat(),
            "assignee": "Engineer B",
        },
    )
    assert second_resp.status_code == 201, second_resp.text
    second = second_resp.json()

    patch_resp = await client.patch(
        "/project-manager/api/subcomponents/actions/batch",
        json={
            "subcomponent_ids": [first["subcomponent_id"], second["subcomponent_id"]],
            "status": "in_progress",
            "assignee": "Engineer Z",
            "assignee_user_soeid": "ez99999",
            "blocked": True,
            "due_date_shift_days": 5,
        },
    )
    assert patch_resp.status_code == 200, patch_resp.text
    updated = patch_resp.json()
    assert len(updated) == 2
    for row in updated:
        assert row["status"] == "in_progress"
        assert row["assignee"] == "Engineer Z"
        assert row["assignee_user_soeid"] == "ez99999"
        assert row["blocked"] is True
        assert row["due_date"] is not None


@pytest.mark.anyio
async def test_batch_reopening_subcomponents_clears_completed_at(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    created_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Batch Reopen Task",
            "status": "complete",
            "assignee": "Engineer A",
        },
    )
    assert created_resp.status_code == 201, created_resp.text
    created = created_resp.json()
    assert created["completed_at"] is not None

    reopened_resp = await client.patch(
        "/project-manager/api/subcomponents/actions/batch",
        json={
            "subcomponent_ids": [created["subcomponent_id"]],
            "status": "in_progress",
        },
    )
    assert reopened_resp.status_code == 200, reopened_resp.text
    reopened = reopened_resp.json()
    assert len(reopened) == 1
    assert reopened[0]["status"] == "in_progress"
    assert reopened[0]["completed_at"] is None


@pytest.mark.anyio
async def test_update_subcomponent_status_logs_completed_at_audit_field(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    created_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Audit Completion Task",
            "status": "to_do",
            "assignee": "Engineer A",
        },
    )
    assert created_resp.status_code == 201, created_resp.text
    created = created_resp.json()

    update_resp = await client.patch(
        f"/project-manager/api/subcomponents/{created['subcomponent_id']}",
        json={"status": "complete"},
    )
    assert update_resp.status_code == 200, update_resp.text
    updated = update_resp.json()
    assert updated["completed_at"] is not None

    audit_resp = await client.get(
        "/project-manager/api/audit",
        params={
            "entity_type": "subcomponent",
            "entity_id": created["subcomponent_id"],
            "field": "completed_at",
        },
    )
    assert audit_resp.status_code == 200, audit_resp.text
    rows = audit_resp.json()
    assert any(row["new_value"] for row in rows)


@pytest.mark.anyio
async def test_batch_update_subcomponents_preserves_inherited_repo_metadata(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    project, _ = await create_project_solution(client)

    solution_resp = await client.post(
        f"/project-manager/api/projects/{project['project_id']}/solutions",
        json={
            "solution_name": "Batch Repo Solution",
            "version": "1.0.0",
            "owner": "Solution Owner",
            "github_repo_url": "https://github.com/example-org/platform-service",
        },
    )
    assert solution_resp.status_code == 201, solution_resp.text
    solution = solution_resp.json()

    created_resp = await client.post(
        f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
        json={
            "subcomponent_name": "Batch Repo Task",
            "status": "to_do",
            "assignee": "Engineer A",
        },
    )
    assert created_resp.status_code == 201, created_resp.text
    created = created_resp.json()
    assert created["effective_github_repo_url"] == "https://github.com/example-org/platform-service"
    assert created["repo_source"] == "inherited"

    batch_resp = await client.patch(
        "/project-manager/api/subcomponents/actions/batch",
        json={
            "subcomponent_ids": [created["subcomponent_id"]],
            "status": "in_progress",
        },
    )
    assert batch_resp.status_code == 200, batch_resp.text
    rows = batch_resp.json()
    assert len(rows) == 1
    assert rows[0]["effective_github_repo_url"] == "https://github.com/example-org/platform-service"
    assert rows[0]["repo_source"] == "inherited"


@pytest.mark.anyio
async def test_member_can_view_subcomponent_activity(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-subcomponent-activity",
            space_name="Subcomponent Activity Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        _, solution = await create_project_solution(client)
        create_resp = await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Activity Task", "status": "to_do"},
        )
        assert create_resp.status_code == 201, create_resp.text
        subcomponent_id = create_resp.json()["subcomponent_id"]
        update_resp = await client.patch(
            f"/project-manager/api/subcomponents/{subcomponent_id}",
            json={"status": "in_progress", "blocked": True},
        )
        assert update_resp.status_code == 200, update_resp.text

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-subcomponent-activity",
            space_name="Subcomponent Activity Space",
            is_global_admin=False,
            space_role="member",
        )
        activity_resp = await client.get(f"/project-manager/api/subcomponents/{subcomponent_id}/activity")
        assert activity_resp.status_code == 200, activity_resp.text
        rows = activity_resp.json()
        assert len(rows) >= 2
        actions = {row.get("action") for row in rows}
        assert "create" in actions
        assert "update" in actions
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space


@pytest.mark.anyio
async def test_subcomponent_uniqueness_and_soft_delete(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    _, solution = await create_project_solution(client)

    payload = {"subcomponent_name": "Billing UI", "assignee": "Engineer A"}
    assert (await client.post(f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents", json=payload)).status_code == 201
    dup = await client.post(f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents", json=payload)
    assert dup.status_code == 400

    # soft delete
    created = (await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents")).json()[0]
    delete_resp = await client.delete(f"/project-manager/api/subcomponents/{created['subcomponent_id']}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/project-manager/api/subcomponents/{created['subcomponent_id']}")
    assert get_resp.status_code == 404

    list_resp = await client.get(f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents")
    assert list_resp.status_code == 200
    assert list_resp.json() == []


@pytest.mark.anyio
async def test_soft_deleted_project_hides_subcomponent_reads_and_clears_subcomponent_cache(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    clear_cache()
    try:
        project, solution = await create_project_solution(client)
        create_resp = await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Hidden Child Task", "assignee": "Engineer A"},
        )
        assert create_resp.status_code == 201, create_resp.text
        subcomponent = create_resp.json()

        primed_list = await client.get("/project-manager/api/subcomponents")
        assert primed_list.status_code == 200, primed_list.text
        assert [row["subcomponent_id"] for row in primed_list.json()] == [subcomponent["subcomponent_id"]]

        primed_solution_list = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents"
        )
        assert primed_solution_list.status_code == 200, primed_solution_list.text
        assert [row["subcomponent_id"] for row in primed_solution_list.json()] == [subcomponent["subcomponent_id"]]

        primed_detail = await client.get(
            f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}"
        )
        assert primed_detail.status_code == 200, primed_detail.text

        primed_export = await client.get("/project-manager/api/subcomponents/export")
        assert primed_export.status_code == 200, primed_export.text
        assert "Hidden Child Task" in primed_export.text

        delete_resp = await client.delete(f"/project-manager/api/projects/{project['project_id']}")
        assert delete_resp.status_code == 204, delete_resp.text

        list_resp = await client.get("/project-manager/api/subcomponents")
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json() == []

        solution_list_resp = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents"
        )
        assert solution_list_resp.status_code == 404, solution_list_resp.text
        assert solution_list_resp.json()["detail"] == "Solution not found"

        detail_resp = await client.get(
            f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}"
        )
        assert detail_resp.status_code == 404, detail_resp.text
        assert detail_resp.json()["detail"] == "Subcomponent not found"

        export_resp = await client.get("/project-manager/api/subcomponents/export")
        assert export_resp.status_code == 200, export_resp.text
        assert "Hidden Child Task" not in export_resp.text
    finally:
        clear_cache()


@pytest.mark.anyio
async def test_soft_deleted_solution_hides_subcomponent_reads_and_clears_subcomponent_cache(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    clear_cache()
    try:
        _project, solution = await create_project_solution(client)
        create_resp = await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Hidden After Solution Delete", "assignee": "Engineer A"},
        )
        assert create_resp.status_code == 201, create_resp.text
        subcomponent = create_resp.json()

        primed_list = await client.get("/project-manager/api/subcomponents")
        assert primed_list.status_code == 200, primed_list.text
        assert [row["subcomponent_id"] for row in primed_list.json()] == [subcomponent["subcomponent_id"]]

        primed_solution_list = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents"
        )
        assert primed_solution_list.status_code == 200, primed_solution_list.text
        assert [row["subcomponent_id"] for row in primed_solution_list.json()] == [subcomponent["subcomponent_id"]]

        primed_detail = await client.get(
            f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}"
        )
        assert primed_detail.status_code == 200, primed_detail.text

        delete_resp = await client.delete(f"/project-manager/api/solutions/{solution['solution_id']}")
        assert delete_resp.status_code == 204, delete_resp.text

        list_resp = await client.get("/project-manager/api/subcomponents")
        assert list_resp.status_code == 200, list_resp.text
        assert list_resp.json() == []

        solution_list_resp = await client.get(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents"
        )
        assert solution_list_resp.status_code == 404, solution_list_resp.text
        assert solution_list_resp.json()["detail"] == "Solution not found"

        detail_resp = await client.get(
            f"/project-manager/api/subcomponents/{subcomponent['subcomponent_id']}"
        )
        assert detail_resp.status_code == 404, detail_resp.text
        assert detail_resp.json()["detail"] == "Subcomponent not found"
    finally:
        clear_cache()


@pytest.mark.anyio
async def test_member_can_delete_subcomponent(client, db_sessionmaker):
    seed_phases(db_sessionmaker)
    original_current_space = fastapi_app.dependency_overrides.get(deps_module.current_space)
    try:
        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-subcomponent",
            space_name="Delete Subcomponent Space",
            is_global_admin=False,
            space_role="space_admin",
        )
        _, solution = await create_project_solution(client)
        create_resp = await client.post(
            f"/project-manager/api/solutions/{solution['solution_id']}/subcomponents",
            json={"subcomponent_name": "Delete Guard Subcomponent"},
        )
        assert create_resp.status_code == 201, create_resp.text
        subcomponent_id = create_resp.json()["subcomponent_id"]

        fastapi_app.dependency_overrides[deps_module.current_space] = lambda: SpaceContext(
            space_id="space-delete-subcomponent",
            space_name="Delete Subcomponent Space",
            is_global_admin=False,
            space_role="member",
        )
        allowed = await client.delete(f"/project-manager/api/subcomponents/{subcomponent_id}")
        assert allowed.status_code == 204, allowed.text
    finally:
        if original_current_space is None:
            fastapi_app.dependency_overrides.pop(deps_module.current_space, None)
        else:
            fastapi_app.dependency_overrides[deps_module.current_space] = original_current_space
