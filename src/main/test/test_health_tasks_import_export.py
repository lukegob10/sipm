from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import event

from backend.app.models import Program, Project, Solution, Space, Task, User
from backend.app.routes.tasks import import_export as task_import
from backend.app.services.spaces import SpaceContext


def _seed(session, actor):
    ctx = SpaceContext(
        space_id="csv-space", space_name="CSV", space_role="space_admin", is_global_admin=True
    )
    session.add_all([
        User(
            user_id=actor.user_id, soeid=actor.soeid, email="csv@example.invalid",
            display_name=actor.display_name, password_hash="unused", role="global_admin", is_active=True,
        ),
        Space(space_id=ctx.space_id, name=ctx.space_name, slug="csv-space"),
        Program(program_id="program", space_id=ctx.space_id, program_name="Program"),
        Project(
            project_id="project", space_id=ctx.space_id, program_id="program", project_name="Project",
            sponsor="Owner", owner="Owner",
        ),
        Solution(
            solution_id="solution", space_id=ctx.space_id, project_id="project",
            solution_name="Solution", version="1", owner="Owner", assignee="Owner",
        ),
        Task(
            task_id="existing", space_id=ctx.space_id, project_id="project", solution_id="solution",
            task_name="Existing", description="Before", assignee="Owner",
        ),
    ])
    session.commit()
    return ctx


def test_task_import_does_not_reload_expired_parent_ids(db_sessionmaker, test_user):
    with db_sessionmaker() as session:
        ctx = _seed(session, test_user)
        parent_selects = {Project: 0, Solution: 0}

        def count_parent_selects(state):
            if state.is_select:
                descriptions = getattr(state.statement, "column_descriptions", ())
                entity = descriptions[0].get("entity") if descriptions else None
                if entity in parent_selects:
                    parent_selects[entity] += 1

        event.listen(session, "do_orm_execute", count_parent_selects)
        result = task_import.import_tasks(
            b"project_name,solution_name,version,task_name\n"
            b"Project,Solution,1,Existing\nProject,Solution,1,New A\nProject,Solution,1,New B\n",
            session=session, current_user=test_user, space_ctx=ctx,
        )
        event.remove(session, "do_orm_execute", count_parent_selects)

        assert result["updated"] == 1
        assert result["created"] == 2
        assert result["errors"] == []
        # One snapshot and one locked refresh per parent for each of three rows.
        assert parent_selects == {Project: 4, Solution: 4}


def test_task_import_dry_run_matches_parent_and_task_counts(db_sessionmaker, test_user):
    csv_bytes = (
        b"project_name,solution_name,version,task_name,description\n"
        b"Project,Solution,1,Existing,After\nProject,Solution,1,New,Created\n"
        b"New Project,New Solution,1,First,Created\nNew Project,New Solution,1,Second,Created\n"
        b"Project,New Solution,1,Third,Created\n"
    )
    with db_sessionmaker() as session:
        ctx = _seed(session, test_user)
        preview = task_import.import_tasks(
            csv_bytes, dry_run=True, session=session, current_user=test_user, space_ctx=ctx,
        )
        assert preview == {
            "created": 4, "updated": 1, "projects_created": 1, "solutions_created": 2,
            "errors": [], "total_rows": 5, "dry_run": True,
        }
        assert session.query(Project).count() == 1
        assert session.query(Solution).count() == 1
        assert session.query(Task).count() == 1
        assert session.get(Task, "existing").description == "Before"

        applied = task_import.import_tasks(
            csv_bytes, session=session, current_user=test_user, space_ctx=ctx,
        )
        assert applied == {**preview, "dry_run": False}
        assert session.query(Project).count() == 2
        assert session.query(Solution).count() == 3
        assert session.query(Task).count() == 5
        assert session.get(Task, "existing").description == "After"


@pytest.mark.parametrize("entity", ["project", "solution"])
@pytest.mark.parametrize("change", ["renamed", "deleted", "missing"])
def test_task_import_revalidates_cached_parents_after_row_commit(
    db_sessionmaker, test_user, monkeypatch, entity, change
):
    with db_sessionmaker() as session:
        ctx = _seed(session, test_user)
        if entity == "project":
            model, target_id, name_field = Project, "second-project", "project_name"
            session.add(Project(
                project_id=target_id, space_id=ctx.space_id, program_id="program",
                project_name="Second Project", sponsor="Owner", owner="Owner",
            ))
            second_row = b"Second Project,New Solution,1,Second\n"
        else:
            model, target_id, name_field = Solution, "second-solution", "solution_name"
            session.add(Solution(
                solution_id=target_id, space_id=ctx.space_id, project_id="project",
                solution_name="Second Solution", version="1", owner="Owner", assignee="Owner",
            ))
            second_row = b"Project,Second Solution,1,Second\n"
        session.commit()
        lock = task_import.lock_work_space
        lock_calls = 0

        def change_parent_before_second_lock(db, space_ctx, actor):
            nonlocal lock_calls
            lock_calls += 1
            if lock_calls == 2:
                with db_sessionmaker() as concurrent:
                    target = concurrent.get(model, target_id)
                    if change == "missing":
                        concurrent.delete(target)
                    elif change == "deleted":
                        target.deleted_at = datetime.now(timezone.utc)
                    else:
                        setattr(target, name_field, "Renamed")
                    concurrent.commit()
            return lock(db, space_ctx, actor)

        monkeypatch.setattr(task_import, "lock_work_space", change_parent_before_second_lock)
        result = task_import.import_tasks(
            b"project_name,solution_name,version,task_name\nProject,Solution,1,First\n" + second_row,
            session=session, current_user=test_user, space_ctx=ctx,
        )

        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["projects_created"] == 0
        assert result["solutions_created"] == 0
        assert result["total_rows"] == 2
        assert result["errors"] == [f"Row 3: {entity} changed during import"]
        assert sorted(row.task_name for row in session.query(Task).all()) == ["Existing", "First"]
