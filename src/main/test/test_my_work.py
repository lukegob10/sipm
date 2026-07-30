from datetime import date, datetime, timedelta, timezone

import pytest

from backend.app.models import Program, Project, Solution, Space, Task, UserTaskState
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus, TaskStatus


@pytest.mark.anyio
async def test_preferences_default_and_update(client):
    response = await client.get("/project-manager/api/users/me/preferences")
    assert response.status_code == 200
    assert response.json() == {
        "developer_mode_enabled": False,
        "theme": "dark",
        "has_saved_preferences": False,
    }

    response = await client.patch(
        "/project-manager/api/users/me/preferences",
        json={"developer_mode_enabled": True, "theme": "light"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "developer_mode_enabled": True,
        "theme": "light",
        "has_saved_preferences": True,
    }

    for theme in ("midnight", "slate", "system"):
        response = await client.patch(
            "/project-manager/api/users/me/preferences",
            json={"theme": theme},
        )
        assert response.status_code == 200
        assert response.json() == {
            "developer_mode_enabled": True,
            "theme": theme,
            "has_saved_preferences": True,
        }

    legacy = await client.patch(
        "/project-manager/api/users/me/preferences",
        json={"theme": "forest"},
    )
    assert legacy.status_code == 200
    assert legacy.json()["theme"] == "slate"

    await client.patch(
        "/project-manager/api/users/me/preferences",
        json={"theme": "system"},
    )

    invalid = await client.patch(
        "/project-manager/api/users/me/preferences",
        json={"theme": "sepia"},
    )
    assert invalid.status_code == 422

    persisted = await client.get("/project-manager/api/users/me/preferences")
    assert persisted.json() == {
        "developer_mode_enabled": True,
        "theme": "system",
        "has_saved_preferences": True,
    }


@pytest.mark.anyio
async def test_my_work_is_assigned_active_context_with_private_queue_order(client, db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(space_id="test-space", name="Test Space", slug="test-space")
        program = Program(program_id="program-1", space_id=space.space_id, program_name="Developer Experience")
        project = Project(
            project_id="project-1",
            space_id=space.space_id,
            program_id=program.program_id,
            project_name="Developer Mode",
            status=ProjectStatus.active,
            sponsor="Test User",
        )
        solution = Solution(
            solution_id="solution-1",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_name="My Work",
            status=SolutionStatus.active,
            rag_status=RagStatus.green,
            owner="Test User",
            assignee="Test User",
            github_repo_url="https://github.com/example/sipm",
        )
        assigned = Task(
            task_id="task-assigned",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Build focused queue",
            status=TaskStatus.to_do,
            priority=1,
            due_date=date.today() + timedelta(days=3),
            assignee="Test User",
            assignee_user_soeid="tu12345",
        )
        blocked = Task(
            task_id="task-blocked",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Resolve API contract",
            status=TaskStatus.in_progress,
            priority=2,
            blocked=True,
            blocker_note="Needs product decision",
            assignee="Test User",
            assignee_user_soeid="tu12345",
        )
        completed = Task(
            task_id="task-completed",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Completed work",
            status=TaskStatus.complete,
            assignee="Test User",
            assignee_user_soeid="tu12345",
        )
        someone_else = Task(
            task_id="task-someone-else",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Other person's work",
            status=TaskStatus.to_do,
            assignee="Another User",
            assignee_user_soeid="au12345",
            github_repo_url="https://github.com/example/other-service",
        )
        session.add_all([space, program, project, solution, assigned, blocked, completed, someone_else])
        session.commit()

    response = await client.get("/project-manager/api/my-work", headers={"X-Space-Id": "test-space"})
    assert response.status_code == 200
    records = response.json()
    assert [record["task"]["task_id"] for record in records] == [
        "task-blocked",
        "task-assigned",
        "task-completed",
    ]
    assert records[0]["needs_attention"] is True
    assert records[1]["needs_attention"] is False
    assert records[1]["program_name"] == "Developer Experience"
    assert records[1]["task"]["effective_github_repo_url"] == "https://github.com/example/sipm"
    assert records[1]["private_bucket"] == "later"
    assert records[1]["private_sort_rank"] == 0
    assert records[1]["private_reminder_at"] is None
    assert records[1]["private_note"] is None
    assert records[1]["reminder_due"] is False

    focused = await client.patch(
        "/project-manager/api/my-work/tasks/task-assigned/state",
        headers={"X-Space-Id": "test-space"},
        json={"sort_rank": 10},
    )
    assert focused.status_code == 200
    assert focused.json() == {
        "task_id": "task-assigned",
        "bucket": "later",
        "sort_rank": 10,
        "reminder_at": None,
        "private_note": None,
    }

    refreshed = await client.get("/project-manager/api/my-work", headers={"X-Space-Id": "test-space"})
    assigned_record = next(row for row in refreshed.json() if row["task"]["task_id"] == "task-assigned")
    assert assigned_record["private_sort_rank"] == 10
    assert assigned_record["needs_attention"] is False

    reset = await client.delete(
        "/project-manager/api/my-work/tasks/task-assigned/state",
        headers={"X-Space-Id": "test-space"},
    )
    assert reset.status_code == 204
    with db_sessionmaker() as session:
        assert session.query(UserTaskState).count() == 0

    inventory_response = await client.get(
        "/project-manager/api/repository-inventory",
        headers={"X-Space-Id": "test-space"},
    )
    assert inventory_response.status_code == 200
    inventory = inventory_response.json()
    assert [row["repository_name"] for row in inventory] == ["example/other-service", "example/sipm"]
    assert inventory[0]["solution_count"] == 1
    assert inventory[0]["task_count"] == 1
    assert inventory[0]["solution_attachment_count"] == 0
    assert inventory[0]["task_override_count"] == 1
    assert inventory[1]["solution_count"] == 1
    assert inventory[1]["task_count"] == 3
    assert inventory[1]["solution_attachment_count"] == 1
    assert inventory[1]["task_override_count"] == 0
    assert inventory[1]["program_names"] == ["Developer Experience"]


@pytest.mark.anyio
async def test_my_work_uses_only_normalized_task_soeid_for_eligibility(client, db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(space_id="test-space", name="Test Space", slug="test-space")
        program = Program(program_id="program-1", space_id=space.space_id, program_name="Program")
        project = Project(
            project_id="project-1",
            space_id=space.space_id,
            program_id=program.program_id,
            project_name="Project",
            status=ProjectStatus.active,
            sponsor="Another User",
            deleted_at=datetime.now(timezone.utc),
        )
        solution = Solution(
            solution_id="solution-1",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_name="Solution",
            status=SolutionStatus.active,
            rag_status=RagStatus.green,
            owner="Another User",
            assignee="Another User",
            assignee_user_soeid="au12345",
            deleted_at=datetime.now(timezone.utc),
        )
        linked = Task(
            task_id="task-linked",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Linked identity",
            status=TaskStatus.to_do,
            assignee="Test User",
            assignee_user_soeid=" TU12345 ",
        )
        legacy = Task(
            task_id="task-legacy",
            space_id=space.space_id,
            project_id=project.project_id,
            solution_id=solution.solution_id,
            task_name="Legacy identity",
            status=TaskStatus.to_do,
            assignee=" TU12345 ",
            assignee_user_soeid=None,
        )
        session.add_all([space, program, project, solution, linked, legacy])
        session.commit()

    response = await client.get("/project-manager/api/my-work", headers={"X-Space-Id": "test-space"})

    assert response.status_code == 200
    assert {record["task"]["task_id"] for record in response.json()} == {"task-linked"}
