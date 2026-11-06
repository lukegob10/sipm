from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Event, local

import pytest
from sqlalchemy.orm import Query

from backend.app.models import Program, Project, Solution, Space, SpaceMembership, Task, User
from backend.app.routes.solutions import write as solution_routes
from backend.app.routes.tasks import import_export as task_import
from backend.app.routes.tasks import write as task_routes
from backend.app.schemas import SolutionUpdate, TaskCreate
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services import agent_patch_plan
from backend.app.services.spaces import SpaceContext


def _setup(db_sessionmaker):
    with db_sessionmaker() as session:
        actor = User(user_id="actor", soeid="actor", email="actor@example.com", display_name="Actor", password_hash="unused", role="user", is_active=True)
        session.add_all([
            actor,
            Space(space_id="race-space", name="Race Space", slug="race-space"),
            SpaceMembership(space_id="race-space", user_id="actor", role="member", status="active"),
            Program(program_id="program", space_id="race-space", program_name="Program"),
            Project(project_id="old", program_id="program", space_id="race-space", project_name="Old"),
            Project(project_id="new", program_id="program", space_id="race-space", project_name="New"),
            Solution(solution_id="solution", project_id="old", space_id="race-space", solution_name="Solution"),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    ctx = SpaceContext(space_id="race-space", space_name="Race Space", is_global_admin=False, space_role="member")
    return actor, ctx


def _move(db_sessionmaker, actor, ctx, mode="interactive"):
    with db_sessionmaker() as session:
        if mode == "agent":
            solution = session.get(Solution, "solution")
            return agent_patch_plan.apply_patch_plan(
                session, ctx, actor, AgentPatchRequest(dry_run=False, reason="Move", idempotency_key="move", operations=[{
                    "client_operation_id": "move", "op": "update", "entity": "solution", "id": "solution",
                    "if_updated_at": solution.updated_at, "fields": {"project_id": "new"},
                }]),
            )
        return solution_routes.update_solution(
            "solution", SolutionUpdate(project_id="new"), session=session, current_user=actor, space_ctx=ctx,
        )


def _create(db_sessionmaker, actor, ctx, mode):
    with db_sessionmaker() as session:
        if mode == "interactive":
            return task_routes.create_task(
                "solution", TaskCreate(task_name="Race Task"), session=session, current_user=actor, space_ctx=ctx,
            )
        if mode == "agent":
            return agent_patch_plan.apply_patch_plan(
                session, ctx, actor,
                AgentPatchRequest(dry_run=False, reason="Race", idempotency_key="race", operations=[{
                    "client_operation_id": "task", "op": "create", "entity": "task", "solution_id": "solution",
                    "fields": {"task_name": "Race Task"},
                }]),
            )
        return task_import.import_tasks(
            b"project_name,solution_name,task_name\nOld,Solution,Race Task\n", dry_run=False,
            session=session, current_user=actor, space_ctx=ctx,
        )


def _assert_consistent(db_sessionmaker, mode):
    with db_sessionmaker() as session:
        solution = session.get(Solution, "solution")
        assert solution.project_id == "new"
        tasks = session.query(Task).filter_by(task_name="Race Task").all()
        # An import may reject a stale CSV hierarchy after the move.
        if mode == "import" and not tasks:
            return
        assert len(tasks) == 1
        task_parent = session.get(Solution, tasks[0].solution_id)
        assert task_parent is not None
        assert tasks[0].project_id == task_parent.project_id


@pytest.mark.parametrize("mode", ["interactive", "agent", "import"])
@pytest.mark.parametrize("move_mode", ["interactive", "agent"])
def test_task_parent_read_racing_solution_move_never_creates_wrong_project(db_sessionmaker, monkeypatch, mode, move_mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("This concurrency test uses SQLite as a local proxy")
    actor, ctx = _setup(db_sessionmaker)
    parent_read = Event()
    release_create = Event()
    thread_state = local()

    if mode in {"interactive", "agent"}:
        module = task_routes if mode == "interactive" else agent_patch_plan
        original = module._ensure_solution

        def pause_parent_read(*args, **kwargs):
            result = original(*args, **kwargs)
            parent_read.set()
            assert release_create.wait(10)
            return result

        monkeypatch.setattr(module, "_ensure_solution", pause_parent_read)
    else:
        original_all = Query.all

        def pause_solution_snapshot(query):
            result = original_all(query)
            if getattr(thread_state, "importing", False) and query.column_descriptions[0]["entity"] is Solution:
                parent_read.set()
                assert release_create.wait(10)
            return result

        monkeypatch.setattr(Query, "all", pause_solution_snapshot)

    def create():
        thread_state.importing = True
        return _create(db_sessionmaker, actor, ctx, mode)

    with ThreadPoolExecutor(max_workers=2) as executor:
        created = executor.submit(create)
        try:
            assert parent_read.wait(10)
            moved = executor.submit(_move, db_sessionmaker, actor, ctx, move_mode)
            # An implementation with parent locking waits here; the old path moves immediately.
            try:
                moved.result(timeout=0.5)
            except TimeoutError:
                pass
        finally:
            release_create.set()
        create_result = created.result(timeout=15)
        move_result = moved.result(timeout=15)
    if move_mode == "agent":
        assert move_result.applied
    if mode == "agent":
        assert create_result.applied
    if mode == "import":
        assert create_result["created"] or create_result["errors"]
    _assert_consistent(db_sessionmaker, mode)


@pytest.mark.parametrize("move_mode", ["interactive", "agent"])
def test_task_create_started_after_move_write_never_uses_stale_parent(db_sessionmaker, monkeypatch, move_mode):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("This concurrency test uses SQLite as a local proxy")
    actor, ctx = _setup(db_sessionmaker)
    move_updated = Event()
    release_move = Event()
    parent_read = Event()
    original_update = Query.update
    original_ensure = task_routes._ensure_solution

    def pause_move(query, *args, **kwargs):
        result = original_update(query, *args, **kwargs)
        if query.column_descriptions[0]["entity"] is Task:
            move_updated.set()
            assert release_move.wait(10)
        return result

    def note_parent(*args, **kwargs):
        result = original_ensure(*args, **kwargs)
        parent_read.set()
        return result

    monkeypatch.setattr(Query, "update", pause_move)
    monkeypatch.setattr(task_routes, "_ensure_solution", note_parent)
    with ThreadPoolExecutor(max_workers=2) as executor:
        moved = executor.submit(_move, db_sessionmaker, actor, ctx, move_mode)
        try:
            assert move_updated.wait(10)
            created = executor.submit(_create, db_sessionmaker, actor, ctx, "interactive")
            # Parent-row locking prevents reading until the move commits.
            parent_read.wait(0.5)
        finally:
            release_move.set()
        move_result = moved.result(timeout=15)
        created.result(timeout=15)
    if move_mode == "agent":
        assert move_result.applied
    _assert_consistent(db_sessionmaker, "interactive")

@pytest.mark.parametrize("mode", ["interactive", "agent"])
def test_task_creation_refreshes_parent_cached_before_space_lock(db_sessionmaker, mode):
    actor, ctx = _setup(db_sessionmaker)
    with db_sessionmaker() as session:
        stale = session.get(Solution, "solution")
        assert stale.project_id == "old"
        _move(db_sessionmaker, actor, ctx)
        if mode == "interactive":
            task_routes.create_task(
                "solution", TaskCreate(task_name="Race Task"), session=session,
                current_user=actor, space_ctx=ctx,
            )
        else:
            result = agent_patch_plan.apply_patch_plan(
                session, ctx, actor,
                AgentPatchRequest(dry_run=False, reason="Race", idempotency_key="race", operations=[{
                    "client_operation_id": "task", "op": "create", "entity": "task", "solution_id": "solution",
                    "fields": {"task_name": "Race Task"},
                }]),
            )
            assert result.applied
    _assert_consistent(db_sessionmaker, mode)


@pytest.mark.parametrize("unavailable", ["missing", "inactive", "deleted"])
def test_space_sentinel_rejects_unavailable_space(db_sessionmaker, unavailable):
    from datetime import datetime
    from fastapi import HTTPException
    from backend.app.services.work_items import lock_work_space

    actor, ctx = _setup(db_sessionmaker)
    with db_sessionmaker() as session:
        space = session.get(Space, ctx.space_id)
        if unavailable == "missing":
            ctx = SpaceContext(space_id="missing", space_name="Missing", is_global_admin=False, space_role="member")
        elif unavailable == "inactive":
            space.is_active = False
        else:
            space.deleted_at = datetime(2026, 1, 1)
        session.commit()
        with pytest.raises(HTTPException) as error:
            lock_work_space(session, ctx, actor)
        assert error.value.status_code == 403


def test_space_lock_does_not_change_updated_at(db_sessionmaker):
    from backend.app.services.work_items import lock_work_space

    actor, ctx = _setup(db_sessionmaker)
    with db_sessionmaker() as session:
        before = session.get(Space, ctx.space_id).updated_at
        lock_work_space(session, ctx, actor)
        session.commit()
        assert session.get(Space, ctx.space_id).updated_at == before


def test_csv_import_reacquires_space_lock_for_each_written_row(db_sessionmaker, monkeypatch):
    actor, ctx = _setup(db_sessionmaker)
    original = task_import.lock_work_space
    calls = []

    def record_lock(session, space_ctx, actor):
        calls.append(space_ctx.space_id)
        return original(session, space_ctx, actor)

    monkeypatch.setattr(task_import, "lock_work_space", record_lock)
    with db_sessionmaker() as session:
        result = task_import.import_tasks(
            b"project_name,solution_name,task_name\nOld,Solution,First\nOld,Solution,Second\n",
            dry_run=False, session=session, current_user=actor, space_ctx=ctx,
        )
    assert result["created"] == 2
    assert not result["errors"]
    assert calls == [ctx.space_id, ctx.space_id]


def test_csv_dry_run_does_not_take_space_write_lock(db_sessionmaker, monkeypatch):
    actor, ctx = _setup(db_sessionmaker)

    def unexpected_lock(*args):
        pytest.fail("dry-run import must not take a write lock")

    monkeypatch.setattr(task_import, "lock_work_space", unexpected_lock)
    with db_sessionmaker() as session:
        result = task_import.import_tasks(
            b"project_name,solution_name,task_name\nOld,Solution,Dry Run\n",
            dry_run=True, session=session, current_user=actor, space_ctx=ctx,
        )
    assert result["created"] == 1
