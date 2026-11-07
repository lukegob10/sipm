from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import event

from backend.app.models import ChangeLog, Program, Project, Solution, Space, Task
from backend.app.services.agent_assigned_work import (
    ASSIGNED_WORK_CURSOR_SCOPE,
    list_agent_assigned_work,
)
from backend.app.services.agent_audit import AUDIT_CURSOR_SCOPE, list_agent_audit_feed
from backend.app.services.agent_pagination import encode_cursor, encode_position_cursor
from backend.app.services.spaces import SpaceContext
from test_agent_api import (
    _auth_headers,
    _seed_agent_token,
    agent_client,  # noqa: F401
    override_db_only,  # noqa: F401
)


def test_assigned_work_fetches_only_needed_parent_context(db_sessionmaker):
    ctx = SpaceContext(
        space_id="health-assigned-space", space_name="Assigned", is_global_admin=False,
        space_role="member",
    )
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id=ctx.space_id, name="Assigned", slug=ctx.space_id),
            Program(program_id="health-program", space_id=ctx.space_id,
                    program_name="Program", description="Unused parent text" * 1000),
            Project(project_id="health-project", program_id="health-program", space_id=ctx.space_id,
                    project_name="Project", description="Unused parent text" * 1000),
            Solution(solution_id="health-solution", project_id="health-project", space_id=ctx.space_id,
                     solution_name="Solution", description="Unused parent text" * 1000,
                     github_repo_url="https://github.com/example/assigned"),
            Task(task_id="health-task", project_id="health-project", solution_id="health-solution",
                 space_id=ctx.space_id, task_name="Task", assignee_user_soeid="assigned"),
        ])
        session.commit()

        fetched_columns = []

        def record_columns(_conn, cursor, _statement, _parameters, _context, _executemany):
            fetched_columns.append(len(cursor.description or ()))

        engine = session.get_bind()
        event.listen(engine, "after_cursor_execute", record_columns)
        try:
            page = list_agent_assigned_work(
                session, ctx, assignee_user_soeid=" Assigned ", cursor=None, limit=10,
            )
        finally:
            event.remove(engine, "after_cursor_execute", record_columns)

    assert fetched_columns == [len(Task.__table__.columns) + 5]
    assert page.assignee_user_soeid == "assigned"
    assert len(page.records) == 1
    item = page.records[0]
    assert (item.program_id, item.program_name, item.project_name, item.solution_name) == (
        "health-program", "Program", "Project", "Solution",
    )
    assert item.task.effective_github_repo_url == "https://github.com/example/assigned"
    assert item.task.repo_source == "inherited"
    assert page.has_more is False


@pytest.mark.anyio
@pytest.mark.parametrize("field,value", [
    ("attention", float("inf")),
    ("priority", float("-inf")),
    ("urgency", float("inf")),
    ("urgency", float("-inf")),
    ("urgency", float("nan")),
])
async def test_assigned_work_rejects_nonfinite_cursor_positions(
    agent_client, db_sessionmaker, field, value,  # noqa: F811
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    position = {
        "attention": 0, "urgency": -100, "due_date": "2026-11-01", "priority": 3,
        "task_name": "Task", "task_id": "task", "as_of": "2026-11-06",
    }
    position[field] = value
    cursor = encode_position_cursor(
        scope=ASSIGNED_WORK_CURSOR_SCOPE,
        filters={"space_id": space_id, "assignee_user_soeid": "assigned"},
        position=position,
    )
    response = await agent_client.get(
        "/project-manager/api/agent/assigned-work", headers=_auth_headers(token, space_id),
        params={"assignee_user_soeid": "assigned", "cursor": cursor},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_CURSOR"


@pytest.mark.anyio
@pytest.mark.parametrize("field", ["since", "until"])
@pytest.mark.parametrize("value", [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59-01:00",
])
async def test_audit_feed_rejects_times_that_overflow_utc(
    agent_client, db_sessionmaker, field, value,  # noqa: F811
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    response = await agent_client.get(
        "/project-manager/api/agent/audit-feed", headers=_auth_headers(token, space_id),
        params={field: value},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_AUDIT_TIME"


@pytest.mark.anyio
@pytest.mark.parametrize("value", [
    "0001-01-01T00:00:00+01:00",
    "9999-12-31T23:59:59-01:00",
])
async def test_audit_feed_rejects_cursor_times_that_overflow_utc(
    agent_client, db_sessionmaker, value,  # noqa: F811
):
    token, space_id = _seed_agent_token(db_sessionmaker)
    cursor = encode_cursor(
        scope=AUDIT_CURSOR_SCOPE,
        filters={
            "space_id": space_id, "requester_user_id": f"user-{space_id}-True-True",
            "since": None, "until": None, "entity_type": None, "entity_id": None,
            "user_id": None, "request_id": None,
        },
        ordered_at=datetime.fromisoformat(value), ordered_id="audit-event",
    )
    response = await agent_client.get(
        "/project-manager/api/agent/audit-feed", headers=_auth_headers(token, space_id),
        params={"cursor": cursor},
    )
    assert response.status_code == 400, response.text
    assert response.json()["code"] == "INVALID_CURSOR"


def test_audit_feed_equivalent_timezones_keep_cursor_binding_and_tie_order(db_sessionmaker):
    ctx = SpaceContext(
        space_id="health-audit-space", space_name="Audit", is_global_admin=False,
        space_role="member",
    )
    stamp = datetime(2026, 11, 6, 12)
    with db_sessionmaker() as session:
        session.add(Space(space_id=ctx.space_id, name="Audit", slug=ctx.space_id))
        session.add_all([
            ChangeLog(change_id=f"health-audit-{index}", entity_type="task", entity_id="task",
                      action="update", user_id="user", space_id=ctx.space_id, created_at=stamp)
            for index in range(3)
        ])
        session.commit()
        first = list_agent_audit_feed(
            session, ctx, requester_user_id="user", limit=1,
            since=stamp.replace(tzinfo=timezone.utc),
        )
        assert first.next_cursor
        second = list_agent_audit_feed(
            session, ctx, requester_user_id="user", limit=2, cursor=first.next_cursor,
            since=(stamp + timedelta(hours=2)).replace(tzinfo=timezone(timedelta(hours=2))),
        )
    assert [row.change_id for row in first.records + second.records] == [
        "health-audit-2", "health-audit-1", "health-audit-0",
    ]
    assert second.has_more is False
