from datetime import datetime, timezone

import pytest

from backend.app.models import Program, Project, Solution, Space, Task, UserTaskState
from backend.app.utils.enums import ProjectStatus, RagStatus, SolutionStatus, TaskStatus


def _seed_assigned_task(session, *, suffix: str = "private", space_id: str = "test-space") -> str:
    space = Space(space_id=space_id, name=f"Space {suffix}", slug=f"space-{suffix}")
    program = Program(
        program_id=f"program-{suffix}",
        space_id=space_id,
        program_name=f"Program {suffix}",
    )
    project = Project(
        project_id=f"project-{suffix}",
        space_id=space_id,
        program_id=program.program_id,
        project_name=f"Project {suffix}",
        status=ProjectStatus.active,
        sponsor="Test User",
    )
    solution = Solution(
        solution_id=f"solution-{suffix}",
        space_id=space_id,
        project_id=project.project_id,
        solution_name=f"Solution {suffix}",
        status=SolutionStatus.active,
        rag_status=RagStatus.green,
        owner="Test User",
        assignee="Test User",
    )
    task = Task(
        task_id=f"task-{suffix}",
        space_id=space_id,
        project_id=project.project_id,
        solution_id=solution.solution_id,
        task_name=f"Task {suffix}",
        status=TaskStatus.to_do,
        assignee="Test User",
        assignee_user_soeid="tu12345",
    )
    session.add_all([space, program, project, solution, task])
    session.commit()
    return task.task_id


@pytest.mark.anyio
async def test_my_work_private_state_patch_is_partial_and_normalizes_utc(client, db_sessionmaker):
    with db_sessionmaker() as session:
        task_id = _seed_assigned_task(session)

    saved = await client.patch(
        f"/project-manager/api/my-work/tasks/{task_id}/state",
        headers={"X-Space-Id": "test-space"},
        json={
            "bucket": "today",
            "sort_rank": 250,
            "reminder_at": "2020-01-02T12:30:00-05:00",
            "private_note": "  Keep this planning note private.  ",
        },
    )

    assert saved.status_code == 200, saved.text
    saved_body = saved.json()
    assert saved_body["task_id"] == task_id
    assert saved_body["bucket"] == "today"
    assert saved_body["sort_rank"] == 250
    assert saved_body["private_note"] == "Keep this planning note private."
    reminder = datetime.fromisoformat(saved_body["reminder_at"].replace("Z", "+00:00"))
    assert reminder == datetime(2020, 1, 2, 17, 30, tzinfo=timezone.utc)

    reordered = await client.patch(
        f"/project-manager/api/my-work/tasks/{task_id}/state",
        headers={"X-Space-Id": "test-space"},
        json={"sort_rank": 900},
    )
    assert reordered.status_code == 200, reordered.text
    assert reordered.json()["bucket"] == "today"
    assert reordered.json()["sort_rank"] == 900
    assert reordered.json()["private_note"] == "Keep this planning note private."
    assert reordered.json()["reminder_at"] == saved_body["reminder_at"]

    refreshed = await client.get(
        "/project-manager/api/my-work",
        headers={"X-Space-Id": "test-space"},
    )
    assert refreshed.status_code == 200, refreshed.text
    record = refreshed.json()[0]
    assert record["private_bucket"] == "today"
    assert record["private_sort_rank"] == 900
    assert record["private_note"] == "Keep this planning note private."
    assert record["private_reminder_at"] == saved_body["reminder_at"]
    assert record["reminder_due"] is True
    assert record["needs_attention"] is True

    cleared = await client.patch(
        f"/project-manager/api/my-work/tasks/{task_id}/state",
        headers={"X-Space-Id": "test-space"},
        json={"reminder_at": None, "private_note": "   "},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["bucket"] == "today"
    assert cleared.json()["sort_rank"] == 900
    assert cleared.json()["reminder_at"] is None
    assert cleared.json()["private_note"] is None

    with db_sessionmaker() as session:
        state = session.query(UserTaskState).one()
        assert state.bucket == "today"
        assert state.sort_rank == 900
        assert state.reminder_at is None
        assert state.private_note is None


@pytest.mark.anyio
async def test_closed_my_work_never_needs_attention(client, db_sessionmaker):
    with db_sessionmaker() as session:
        task_id = _seed_assigned_task(session, suffix="closed-attention")
        task = session.get(Task, task_id)
        task.status = TaskStatus.complete
        task.blocked = True
        session.add(
            UserTaskState(
                user_id="test-user",
                space_id="test-space",
                task_id=task_id,
                reminder_at=datetime(2020, 1, 1, 12, 0),
            )
        )
        session.commit()

    for closed_status in (TaskStatus.complete, TaskStatus.abandoned):
        with db_sessionmaker() as session:
            task = session.get(Task, task_id)
            task.status = closed_status
            session.commit()

        response = await client.get(
            "/project-manager/api/my-work",
            headers={"X-Space-Id": "test-space"},
        )
        assert response.status_code == 200, response.text
        assert response.json()[0]["reminder_due"] is True
        assert response.json()[0]["needs_attention"] is False


@pytest.mark.anyio
async def test_my_work_private_state_rejects_invalid_values(client, db_sessionmaker):
    with db_sessionmaker() as session:
        task_id = _seed_assigned_task(session, suffix="validation")

    invalid_payloads = [
        {"bucket": "waiting"},
        {"bucket": None},
        {"sort_rank": -1},
        {"sort_rank": None},
        {"reminder_at": "2026-07-29T12:00:00"},
        {"private_note": 123},
        {"private_note": "x" * 10_001},
    ]
    for payload in invalid_payloads:
        response = await client.patch(
            f"/project-manager/api/my-work/tasks/{task_id}/state",
            headers={"X-Space-Id": "test-space"},
            json=payload,
        )
        assert response.status_code == 422, (payload, response.text)

    no_op = await client.patch(
        f"/project-manager/api/my-work/tasks/{task_id}/state",
        headers={"X-Space-Id": "test-space"},
        json={},
    )
    assert no_op.status_code == 200, no_op.text
    assert no_op.json() == {
        "task_id": task_id,
        "bucket": "later",
        "sort_rank": 0,
        "reminder_at": None,
        "private_note": None,
    }
    with db_sessionmaker() as session:
        assert session.query(UserTaskState).count() == 0


@pytest.mark.anyio
async def test_my_work_private_state_is_scoped_by_user_space_and_task(client, db_sessionmaker):
    with db_sessionmaker() as session:
        active_task_id = _seed_assigned_task(session, suffix="active")
        other_task_id = _seed_assigned_task(
            session,
            suffix="other",
            space_id="other-space",
        )
        session.add_all(
            [
                UserTaskState(
                    user_id="other-user",
                    space_id="test-space",
                    task_id=active_task_id,
                    bucket="today",
                    sort_rank=10,
                    private_note="Another user's private note",
                ),
                UserTaskState(
                    user_id="test-user",
                    space_id="other-space",
                    task_id=other_task_id,
                    bucket="today",
                    sort_rank=20,
                    private_note="Another space's private note",
                ),
            ]
        )
        session.commit()

    listing = await client.get(
        "/project-manager/api/my-work",
        headers={"X-Space-Id": "test-space"},
    )
    assert listing.status_code == 200, listing.text
    assert len(listing.json()) == 1
    assert listing.json()[0]["task"]["task_id"] == active_task_id
    assert listing.json()[0]["private_bucket"] == "later"
    assert listing.json()[0]["private_note"] is None

    wrong_space_update = await client.patch(
        f"/project-manager/api/my-work/tasks/{other_task_id}/state",
        headers={"X-Space-Id": "test-space"},
        json={"sort_rank": 999},
    )
    assert wrong_space_update.status_code == 404

    wrong_space_delete = await client.delete(
        f"/project-manager/api/my-work/tasks/{other_task_id}/state",
        headers={"X-Space-Id": "test-space"},
    )
    assert wrong_space_delete.status_code == 204
    with db_sessionmaker() as session:
        states = session.query(UserTaskState).all()
        assert len(states) == 2
        assert {state.private_note for state in states} == {
            "Another user's private note",
            "Another space's private note",
        }
