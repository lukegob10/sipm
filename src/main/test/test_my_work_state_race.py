from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from backend.app.models import Program, Project, Solution, Space, Task, UserPreference, UserTaskState
from backend.app.routes.my_work import update_my_preferences, update_my_work_state
from backend.app.schemas import UserPreferenceUpdate, UserTaskStateUpdate
from backend.app.services.spaces import SpaceContext


def _seed(db_sessionmaker):
    actor = SimpleNamespace(user_id="user", soeid="developer")
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space", name="Space", slug="space"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", program_id="program", space_id="space", project_name="Project"),
            Solution(solution_id="solution", project_id="project", space_id="space", solution_name="Solution"),
            Task(task_id="task", solution_id="solution", project_id="project", space_id="space",
                 task_name="Task", assignee_user_soeid="developer"),
        ])
        session.commit()
    return actor, ctx


def test_concurrent_first_private_state_updates_preserve_both_changes(db_sessionmaker):
    actor, ctx = _seed(db_sessionmaker)

    def other_tab_saves_first(_session, _context, _instances):
        with db_sessionmaker() as other:
            update_my_work_state("task", UserTaskStateUpdate(bucket="today"), session=other,
                                 space_ctx=ctx, current_user=actor)

    with db_sessionmaker() as session:
        event.listen(session, "before_flush", other_tab_saves_first, once=True)
        result = update_my_work_state("task", UserTaskStateUpdate(private_note="private note"),
                                      session=session, space_ctx=ctx, current_user=actor)
        assert result.bucket == "today"
        assert result.private_note == "private note"

    with db_sessionmaker() as session:
        state = session.query(UserTaskState).one()
        assert state.bucket == "today"
        assert state.private_note == "private note"


def test_retry_checks_task_is_still_assigned(db_sessionmaker):
    actor, ctx = _seed(db_sessionmaker)

    def other_tab_saves_and_reassigns(_session, _context, _instances):
        with db_sessionmaker() as other:
            update_my_work_state("task", UserTaskStateUpdate(bucket="today"), session=other,
                                 space_ctx=ctx, current_user=actor)
            other.get(Task, "task").assignee_user_soeid = "someone-else"
            other.commit()

    with db_sessionmaker() as session:
        event.listen(session, "before_flush", other_tab_saves_and_reassigns, once=True)
        with pytest.raises(HTTPException) as error:
            update_my_work_state("task", UserTaskStateUpdate(private_note="private note"),
                                 session=session, space_ctx=ctx, current_user=actor)
        assert error.value.status_code == 404
    with db_sessionmaker() as session:
        assert session.query(UserTaskState).one().private_note is None


def test_unrelated_insert_conflict_is_not_hidden(db_sessionmaker, monkeypatch):
    actor, ctx = _seed(db_sessionmaker)
    with db_sessionmaker() as session:
        def fail_commit():
            raise IntegrityError("insert", {}, RuntimeError("unrelated constraint"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError, match="unrelated constraint"):
            update_my_work_state("task", UserTaskStateUpdate(private_note="private note"),
                                 session=session, space_ctx=ctx, current_user=actor)


def test_concurrent_first_preference_updates_preserve_both_changes(db_sessionmaker):
    actor, _ctx = _seed(db_sessionmaker)

    def other_tab_saves_first(_session, _context, _instances):
        with db_sessionmaker() as other:
            update_my_preferences(UserPreferenceUpdate(developer_mode_enabled=True),
                                  session=other, current_user=actor)

    with db_sessionmaker() as session:
        event.listen(session, "before_flush", other_tab_saves_first, once=True)
        result = update_my_preferences(UserPreferenceUpdate(theme="light"), session=session, current_user=actor)
        assert result.theme == "light"
        assert result.developer_mode_enabled is True
    with db_sessionmaker() as session:
        preference = session.get(UserPreference, "user")
        assert preference.theme == "light"
        assert preference.developer_mode_enabled is True


def test_unrelated_preference_insert_conflict_is_not_hidden(db_sessionmaker, monkeypatch):
    actor, _ctx = _seed(db_sessionmaker)
    with db_sessionmaker() as session:
        def fail_commit():
            raise IntegrityError("insert", {}, RuntimeError("unrelated preference constraint"))

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(IntegrityError, match="unrelated preference constraint"):
            update_my_preferences(UserPreferenceUpdate(theme="light"), session=session, current_user=actor)
