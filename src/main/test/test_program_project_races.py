from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Query

from backend.app.models import Program, Project, Space, SpaceMembership, User
from backend.app.routes import programs
from backend.app.routes.projects import import_export as project_import
from backend.app.routes.projects import write as project_write
from backend.app.routes.solutions import import_export as solution_import
from backend.app.routes.tasks import import_export as task_import
from backend.app.schemas import ProjectCreate, ProjectUpdate
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services import agent_patch_plan
from backend.app.services.spaces import SpaceContext


def setup_space(factory):
    with factory() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor,
            Space(space_id="space", name="Space", slug="space"),
            SpaceMembership(space_id="space", user_id="actor", role="member", status="active"),
            Program(program_id="target", space_id="space", program_name="Default Program"),
            Program(program_id="other", space_id="space", program_name="Other"),
            Project(project_id="existing", space_id="space", program_id="other", project_name="Existing"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    return actor, SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)


def write_project(factory, actor, ctx, mode):
    with factory() as session:
        if mode == "create":
            return project_write.create_project(ProjectCreate(project_name="New", program_id="target"), session=session, current_user=actor, space_ctx=ctx)
        if mode == "move":
            return project_write.update_project("existing", ProjectUpdate(program_id="target"), session=session, current_user=actor, space_ctx=ctx)
        if mode == "project_import":
            return project_import.import_projects(b"project_name,program_id\nNew,target\n", session=session, current_user=actor, space_ctx=ctx)
        if mode == "solution_import":
            return solution_import.import_solutions(b"project_name,solution_name,version\nNew,Solution,1.0\n", session=session, current_user=actor, space_ctx=ctx)
        if mode == "task_import":
            return task_import.import_tasks(b"project_name,solution_name,task_name\nNew,Solution,Task\n", session=session, current_user=actor, space_ctx=ctx)
        return agent_patch_plan.apply_patch_plan(session, ctx, actor, AgentPatchRequest(
            dry_run=False, reason="Create", idempotency_key="create", operations=[{
                "client_operation_id": "create", "op": "create", "entity": "project",
                "fields": {"project_name": "New", "program_id": "target"},
            }],
        ))


def delete_program(factory, actor, ctx, mode="interactive"):
    with factory() as session:
        if mode == "interactive":
            return programs.delete_program("target", session=session, current_user=actor, space_ctx=ctx)
        program = session.get(Program, "target")
        return agent_patch_plan.apply_patch_plan(session, ctx, actor, AgentPatchRequest(
            dry_run=False, reason="Archive", idempotency_key="archive", operations=[{
                "client_operation_id": "archive", "op": "archive", "entity": "program", "id": "target",
                "if_updated_at": program.updated_at,
            }],
        ))


def assert_valid_hierarchy(factory):
    with factory() as session:
        for project in session.query(Project).filter(Project.deleted_at.is_(None)).all():
            parent = session.get(Program, project.program_id)
            assert parent is not None and parent.deleted_at is None
            assert parent.space_id == project.space_id


MODES = ["create", "move", "project_import", "solution_import", "task_import", "agent"]


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("delete_mode", ["interactive", "agent"])
def test_project_write_waits_for_program_deletion(db_sessionmaker, monkeypatch, mode, delete_mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    counted, release = Event(), Event()
    original_count = Query.count

    def pause_count(query):
        result = original_count(query)
        if query.column_descriptions[0].get("entity") is Project:
            counted.set()
            assert release.wait(10)
        return result

    monkeypatch.setattr(Query, "count", pause_count)
    with ThreadPoolExecutor(max_workers=2) as pool:
        deletion = pool.submit(delete_program, db_sessionmaker, actor, ctx, delete_mode)
        try:
            assert counted.wait(10)
            writing = pool.submit(write_project, db_sessionmaker, actor, ctx, mode)
            with pytest.raises(TimeoutError):
                writing.result(timeout=0.25)
        finally:
            release.set()
        delete_result = deletion.result(timeout=15)
        if delete_mode == "agent":
            assert delete_result.applied
        if mode in {"create", "move"}:
            with pytest.raises(HTTPException) as exc:
                writing.result(timeout=15)
            assert exc.value.status_code == 404
        else:
            result = writing.result(timeout=15)
            if mode == "project_import":
                assert result["created"] == 0 and len(result["errors"]) == 1
            elif mode in {"solution_import", "task_import"}:
                assert result["created"] == 1 and not result["errors"]
            else:
                assert not result.applied and not result.valid
    assert_valid_hierarchy(db_sessionmaker)


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("delete_mode", ["interactive", "agent"])
def test_program_deletion_waits_for_project_write(db_sessionmaker, monkeypatch, mode, delete_mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    locked, release = Event(), Event()
    module = {
        "create": project_write, "move": project_write, "project_import": project_import,
        "solution_import": solution_import, "task_import": task_import, "agent": agent_patch_plan,
    }[mode]
    original_lock = module.lock_work_space

    def pause_after_lock(*args, **kwargs):
        original_lock(*args, **kwargs)
        locked.set()
        assert release.wait(10)

    monkeypatch.setattr(module, "lock_work_space", pause_after_lock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(write_project, db_sessionmaker, actor, ctx, mode)
        try:
            assert locked.wait(10)
            deletion = pool.submit(delete_program, db_sessionmaker, actor, ctx, delete_mode)
            with pytest.raises(TimeoutError):
                deletion.result(timeout=0.25)
        finally:
            release.set()
        result = writing.result(timeout=15)
        if mode.endswith("import"):
            assert result["created"] == 1 and not result["errors"]
        if mode == "agent":
            assert result.applied
        if delete_mode == "interactive":
            with pytest.raises(HTTPException) as exc:
                deletion.result(timeout=15)
            assert exc.value.status_code == 400
        else:
            delete_result = deletion.result(timeout=15)
            assert not delete_result.valid and delete_result.results[0].code == "ACTIVE_CHILDREN"
    assert_valid_hierarchy(db_sessionmaker)


@pytest.mark.parametrize("mode", ["project_import", "solution_import"])
def test_import_stops_after_access_is_revoked_between_rows(db_sessionmaker, monkeypatch, mode):
    actor, ctx = setup_space(db_sessionmaker)
    module = project_import if mode == "project_import" else solution_import
    original_lock = module.lock_work_space
    lock_count = 0

    def revoke_before_second_lock(session, space_ctx, user):
        nonlocal lock_count
        lock_count += 1
        if lock_count == 2:
            with db_sessionmaker() as other:
                other.query(SpaceMembership).filter_by(space_id="space", user_id="actor").one().status = "inactive"
                other.commit()
        original_lock(session, space_ctx, user)

    monkeypatch.setattr(module, "lock_work_space", revoke_before_second_lock)
    with db_sessionmaker() as session:
        if mode == "project_import":
            result = module.import_projects(b"project_name,program_id\nFirst,target\nSecond,target\n", session=session, current_user=actor, space_ctx=ctx)
        else:
            result = module.import_solutions(b"project_name,solution_name,version\nFirst,Solution,1\nSecond,Solution,1\n", session=session, current_user=actor, space_ctx=ctx)
    assert result["created"] == 1
    assert result["errors"] == ["Row 3: import stopped because access to the space changed"]
    with db_sessionmaker() as session:
        assert session.query(Project).filter_by(project_name="First").count() == 1
        assert session.query(Project).filter_by(project_name="Second").count() == 0


@pytest.mark.parametrize("mode", ["create", "move"])
@pytest.mark.parametrize("apply", [False, True])
def test_agent_project_plan_reports_missing_program(db_sessionmaker, mode, apply):
    actor, ctx = setup_space(db_sessionmaker)
    with db_sessionmaker() as session:
        fields = {"program_id": "missing"}
        operation = {"client_operation_id": "project", "entity": "project", "fields": fields}
        if mode == "create":
            operation.update({"op": "create", "fields": {**fields, "project_name": "New"}})
        else:
            operation.update({"op": "update", "id": "existing", "if_updated_at": session.get(Project, "existing").updated_at})
        payload = AgentPatchRequest(dry_run=not apply, reason="Plan", idempotency_key="plan", operations=[operation])
        if apply:
            result = agent_patch_plan.apply_patch_plan(session, ctx, actor, payload)
        else:
            result = agent_patch_plan.validate_patch_plan(session, ctx, payload)
        assert not result.valid
        assert result.results[0].code == "PROGRAM_NOT_FOUND"
