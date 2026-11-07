from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi import HTTPException

from backend.app.models import Program, Project, Solution, Space, SpaceMembership, Task, User
from backend.app.routes.projects import write as project_write
from backend.app.routes.solutions import import_export as solution_import
from backend.app.routes.solutions import write as solution_write
from backend.app.routes.tasks import import_export as task_import
from backend.app.routes.tasks import write as task_write
from backend.app.schemas import SolutionCreate, TaskCreate
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services import agent_patch_plan
from backend.app.services.spaces import SpaceContext


def setup_space(factory):
    with factory() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor, Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Existing", version="1"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    return actor, SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)


def create_child(factory, actor, ctx, mode):
    with factory() as session:
        if mode == "solution":
            return solution_write.create_solution("project", SolutionCreate(solution_name="New"), session=session, current_user=actor, space_ctx=ctx)
        if mode == "task":
            return task_write.create_task("solution", TaskCreate(task_name="New"), session=session, current_user=actor, space_ctx=ctx)
        if mode == "solution_import":
            return solution_import.import_solutions(b"project_name,solution_name,version\nProject,New,1\n", session=session, current_user=actor, space_ctx=ctx)
        if mode == "task_import":
            return task_import.import_tasks(b"project_name,solution_name,version,task_name\nProject,Existing,1,New\n", session=session, current_user=actor, space_ctx=ctx)
        operation = {"client_operation_id": "create", "op": "create", "fields": {}}
        if mode == "agent_solution":
            operation.update({"entity": "solution", "project_id": "project", "fields": {"solution_name": "New"}})
        else:
            operation.update({"entity": "task", "solution_id": "solution", "fields": {"task_name": "New"}})
        return agent_patch_plan.apply_patch_plan(session, ctx, actor, AgentPatchRequest(
            dry_run=False, reason="Create", idempotency_key="create", operations=[operation],
        ))


def delete_project(factory, actor, ctx, mode="interactive"):
    with factory() as session:
        if mode == "interactive":
            return project_write.delete_project("project", session=session, current_user=actor, space_ctx=ctx)
        project = session.get(Project, "project")
        return agent_patch_plan.apply_patch_plan(session, ctx, actor, AgentPatchRequest(
            dry_run=False, reason="Archive", idempotency_key="archive", operations=[{
                "client_operation_id": "archive", "op": "archive", "entity": "project", "id": "project",
                "if_updated_at": project.updated_at,
            }],
        ))


MODES = ["solution", "task", "solution_import", "task_import", "agent_solution", "agent_task"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("delete_mode", ["interactive", "agent"])
def test_child_creation_waits_for_project_deletion(db_sessionmaker, monkeypatch, mode, delete_mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    checked, release = Event(), Event()
    delete_module = project_write if delete_mode == "interactive" else agent_patch_plan
    delete_lookup = "_get_project_or_404" if delete_mode == "interactive" else "_active_entity"
    original = getattr(delete_module, delete_lookup)

    def pause_delete(*args, **kwargs):
        result = original(*args, **kwargs)
        checked.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(delete_module, delete_lookup, pause_delete)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(delete_project, db_sessionmaker, actor, ctx, delete_mode)
        try:
            assert checked.wait(10)
            creation = pool.submit(create_child, db_sessionmaker, actor, ctx, mode)
            with pytest.raises(TimeoutError):
                creation.result(timeout=0.25)
        finally:
            release.set()
        delete_result = deletion.result(timeout=15)
        if delete_mode == "agent":
            assert delete_result.applied
        if mode in {"solution", "task"}:
            with pytest.raises(HTTPException) as exc:
                creation.result(timeout=15)
            assert exc.value.status_code == 404
        else:
            result = creation.result(timeout=15)
            if mode.startswith("agent"):
                assert not result.valid
            else:
                assert result["created"] or result["errors"]
    with db_sessionmaker() as session:
        assert session.get(Project, "project").deleted_at is not None
        assert session.query(Solution).filter_by(project_id="project", solution_name="New").count() == 0
        assert session.query(Task).filter_by(project_id="project", task_name="New").count() == 0


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("delete_mode", ["interactive", "agent"])
def test_project_deletion_waits_for_child_creation(db_sessionmaker, monkeypatch, mode, delete_mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    locked, release = Event(), Event()
    module = {
        "solution": solution_write, "task": task_write, "solution_import": solution_import,
        "task_import": task_import, "agent_solution": agent_patch_plan, "agent_task": agent_patch_plan,
    }[mode]
    original = module.lock_work_space

    def pause_create(*args, **kwargs):
        original(*args, **kwargs)
        locked.set()
        assert release.wait(10)

    monkeypatch.setattr(module, "lock_work_space", pause_create)
    with ThreadPoolExecutor(max_workers=2) as pool:
        creation = pool.submit(create_child, db_sessionmaker, actor, ctx, mode)
        try:
            assert locked.wait(10)
            deletion = pool.submit(delete_project, db_sessionmaker, actor, ctx, delete_mode)
            with pytest.raises(TimeoutError):
                deletion.result(timeout=0.25)
        finally:
            release.set()
        result = creation.result(timeout=15)
        if mode.endswith("import"):
            assert result["created"] == 1 and not result["errors"]
        if mode.startswith("agent"):
            assert result.applied
        delete_result = deletion.result(timeout=15)
        if delete_mode == "agent":
            assert delete_result.applied
    with db_sessionmaker() as session:
        assert session.get(Project, "project").deleted_at is not None
        model = Task if "task" in mode else Solution
        name = Task.task_name if model is Task else Solution.solution_name
        assert session.query(model).filter(model.project_id == "project", name == "New").count() == 1
