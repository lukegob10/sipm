from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from backend.app.models import Program, Project, Solution, Space, Task
from backend.app.services import agent_assigned_work, work_items
from backend.app.services.agent_pagination import decode_position_cursor, encode_position_cursor
from backend.app.services.spaces import SpaceContext


class _Clock:
    current = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)

    @classmethod
    def now(cls, _tz=None):
        return cls.current


def _seed(session):
    session.add_all([
        Space(space_id="cursor-space", name="Cursor Space", slug="cursor-space"),
        Program(program_id="cursor-program", space_id="cursor-space", program_name="Program"),
        Project(project_id="cursor-project", space_id="cursor-space", program_id="cursor-program", project_name="Project"),
        Solution(solution_id="cursor-solution", space_id="cursor-space", project_id="cursor-project",
                 solution_name="Solution", version="1"),
        Task(task_id="due", space_id="cursor-space", project_id="cursor-project", solution_id="cursor-solution",
             task_name="Due Today", assignee_user_soeid="assignee", due_date=_Clock.current.date()),
        Task(task_id="blocked", space_id="cursor-space", project_id="cursor-project", solution_id="cursor-solution",
             task_name="Blocked", assignee_user_soeid="assignee", blocked=True),
    ])
    session.commit()


def _page(session, cursor=None):
    return agent_assigned_work.list_agent_assigned_work(
        session,
        SpaceContext(space_id="cursor-space", space_name="Cursor Space", is_global_admin=False, space_role="member"),
        assignee_user_soeid="assignee", cursor=cursor, limit=1,
    )


def test_assigned_work_cursor_preserves_order_across_utc_midnight(db_sessionmaker, monkeypatch):
    _Clock.current = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(work_items, "datetime", _Clock)
    monkeypatch.setattr(agent_assigned_work, "datetime", _Clock, raising=False)
    with db_sessionmaker() as session:
        _seed(session)
        first = _page(session)
        assert [item.task.task_id for item in first.records] == ["blocked"]
        assert first.next_cursor

        _Clock.current = datetime(2026, 1, 11, 0, 1, tzinfo=timezone.utc)
        second = _page(session, first.next_cursor)
        assert [item.task.task_id for item in second.records] == ["due"]
        assert second.records[0].task.is_overdue is False
        assert second.has_more is False


def test_existing_cursor_without_as_of_remains_accepted(db_sessionmaker, monkeypatch):
    _Clock.current = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(work_items, "datetime", _Clock)
    monkeypatch.setattr(agent_assigned_work, "datetime", _Clock, raising=False)
    with db_sessionmaker() as session:
        _seed(session)
        first = _page(session)
        filters = {"space_id": "cursor-space", "assignee_user_soeid": "assignee"}
        position = decode_position_cursor(
            first.next_cursor, scope=agent_assigned_work.ASSIGNED_WORK_CURSOR_SCOPE, filters=filters,
        )
        position.pop("as_of", None)
        legacy_cursor = encode_position_cursor(
            scope=agent_assigned_work.ASSIGNED_WORK_CURSOR_SCOPE, filters=filters, position=position,
        )
        second = _page(session, legacy_cursor)
        assert [item.task.task_id for item in second.records] == ["due"]


@pytest.mark.parametrize("invalid_date", ["not-a-date", None, 20260110])
def test_cursor_with_invalid_as_of_is_rejected(db_sessionmaker, monkeypatch, invalid_date):
    _Clock.current = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(work_items, "datetime", _Clock)
    monkeypatch.setattr(agent_assigned_work, "datetime", _Clock)
    with db_sessionmaker() as session:
        _seed(session)
        first = _page(session)
        filters = {"space_id": "cursor-space", "assignee_user_soeid": "assignee"}
        position = decode_position_cursor(
            first.next_cursor, scope=agent_assigned_work.ASSIGNED_WORK_CURSOR_SCOPE, filters=filters,
        )
        position["as_of"] = invalid_date
        cursor = encode_position_cursor(
            scope=agent_assigned_work.ASSIGNED_WORK_CURSOR_SCOPE, filters=filters, position=position,
        )
        with pytest.raises(HTTPException) as error:
            _page(session, cursor)
        assert error.value.status_code == 400
        assert error.value.headers["X-Error-Code"] == "INVALID_CURSOR"


def test_task_actionability_defaults_to_current_utc_date(monkeypatch):
    _Clock.current = datetime(2026, 1, 10, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(work_items, "datetime", _Clock)
    task = Task(task_id="due", task_name="Due", due_date=_Clock.current.date())
    assert work_items.task_actionability(task)["is_overdue"] is False
    _Clock.current = datetime(2026, 1, 11, 0, 1, tzinfo=timezone.utc)
    assert work_items.task_actionability(task)["is_overdue"] is True
