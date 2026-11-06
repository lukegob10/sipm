from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi import HTTPException

from backend.app.models import Program, Project, Solution, Space, SpaceMembership, Task, User
from backend.app.routes import programs
from backend.app.routes.projects import write as projects
from backend.app.routes.solutions import write as solutions
from backend.app.routes.tasks import write as tasks
from backend.app.schemas import ProgramUpdate, ProjectUpdate, SolutionUpdate, TaskBatchUpdate, TaskUpdate
from backend.app.services.spaces import SpaceContext


def setup_space(factory):
    with factory() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor, Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Program(program_id="empty", space_id="space", program_name="Empty"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Solution", github_repo_url="https://github.com/example/repo"),
            Task(task_id="task", space_id="space", project_id="project", solution_id="solution", task_name="Before"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    return actor, SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)


def write_item(factory, actor, ctx, mode):
    with factory() as session:
        kw = {"session": session, "current_user": actor, "space_ctx": ctx}
        if mode == "program":
            return programs.update_program("empty", ProgramUpdate(program_name="Updated"), **kw)
        if mode == "project":
            return projects.update_project("project", ProjectUpdate(description="Updated"), **kw)
        if mode == "solution":
            return solutions.update_solution("solution", SolutionUpdate(description="Updated"), **kw)
        if mode == "task":
            return tasks.update_task("task", TaskUpdate(task_name="Updated"), **kw)
        if mode == "batch":
            return tasks.batch_update_tasks(TaskBatchUpdate(task_ids=["task"], priority=1), **kw)
        return tasks.delete_task("task", **kw)


def delete_parent(factory, actor, ctx, mode):
    with factory() as session:
        kw = {"session": session, "current_user": actor, "space_ctx": ctx}
        if mode == "program":
            return programs.delete_program("empty", **kw)
        if mode in {"project", "solution"}:
            return projects.delete_project("project", **kw)
        return solutions.delete_solution("solution", **kw)


MODES = ["program", "project", "solution", "task", "batch", "task_delete"]


@pytest.mark.parametrize("mode", MODES)
def test_write_waits_for_parent_or_item_deletion(db_sessionmaker, monkeypatch, mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    checked, release = Event(), Event()
    delete_module = programs if mode == "program" else projects if mode in {"project", "solution"} else solutions
    lookup = "_get_program_or_404" if mode == "program" else "_get_project_or_404" if mode in {"project", "solution"} else "_get_solution_or_404"
    original = getattr(delete_module, lookup)

    def pause_delete(*args, **kwargs):
        result = original(*args, **kwargs)
        checked.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(delete_module, lookup, pause_delete)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(delete_parent, db_sessionmaker, actor, ctx, mode)
        try:
            assert checked.wait(10)
            writing = pool.submit(write_item, db_sessionmaker, actor, ctx, mode)
            with pytest.raises(TimeoutError):
                writing.result(timeout=0.25)
        finally:
            release.set()
        deletion.result(timeout=15)
        with pytest.raises(HTTPException) as exc:
            writing.result(timeout=15)
        assert exc.value.status_code == 404
    with db_sessionmaker() as session:
        if mode == "program":
            assert session.get(Program, "empty").program_name != "Updated"
        if mode == "project":
            assert session.get(Project, "project").description != "Updated"
        if mode == "solution":
            assert session.get(Solution, "solution").description != "Updated"
        if mode == "task":
            assert session.get(Task, "task").task_name == "Before"
        if mode == "batch":
            assert session.get(Task, "task").priority != 1
        if mode == "task_delete":
            assert session.get(Task, "task").deleted_at is None


@pytest.mark.parametrize("mode", MODES)
def test_deletion_waits_for_work_write(db_sessionmaker, monkeypatch, mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    locked, release = Event(), Event()
    module = programs if mode == "program" else projects if mode == "project" else solutions if mode == "solution" else tasks
    original = module.lock_work_space

    def pause_write(*args, **kwargs):
        original(*args, **kwargs)
        locked.set()
        assert release.wait(10)

    monkeypatch.setattr(module, "lock_work_space", pause_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(write_item, db_sessionmaker, actor, ctx, mode)
        try:
            assert locked.wait(10)
            deletion = pool.submit(delete_parent, db_sessionmaker, actor, ctx, mode)
            with pytest.raises(TimeoutError):
                deletion.result(timeout=0.25)
        finally:
            release.set()
        writing.result(timeout=15)
        deletion.result(timeout=15)


@pytest.mark.parametrize("mode", ["task", "batch"])
def test_task_write_response_keeps_committed_parent_data_if_parent_is_deleted(db_sessionmaker, monkeypatch, mode):
    actor, ctx = setup_space(db_sessionmaker)
    target = "commit_refresh_and_publish" if mode == "task" else "commit_session"
    original = getattr(tasks, target)

    def delete_after_commit(*args, **kwargs):
        result = original(*args, **kwargs)
        delete_parent(db_sessionmaker, actor, ctx, "task")
        return result

    monkeypatch.setattr(tasks, target, delete_after_commit)
    result = write_item(db_sessionmaker, actor, ctx, mode)
    row = result if mode == "task" else result[0]
    assert row["effective_github_repo_url"] == "https://github.com/example/repo"
    with db_sessionmaker() as session:
        assert session.get(Solution, "solution").deleted_at is not None
        assert session.get(Task, "task").task_name == ("Updated" if mode == "task" else "Before")
        if mode == "batch":
            assert session.get(Task, "task").priority == 1
