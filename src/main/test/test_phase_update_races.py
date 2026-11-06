from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event

import pytest
from fastapi import HTTPException

from backend.app.models import Phase, Program, Project, Solution, SolutionPhase, Space, SpaceMembership, User
from backend.app.routes import phases
from backend.app.routes.solutions import import_export as solution_import
from backend.app.routes.solutions import write as solution_write
from backend.app.schemas import SolutionUpdate
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
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
            Solution(solution_id="solution", space_id="space", project_id="project", solution_name="Solution", version="1"),
            Phase(phase_id="requirements", phase_group="Requirements", phase_name="Requirements", sequence=2),
            SolutionPhase(solution_id="solution", phase_id="requirements", is_enabled=True),
        ])
        session.commit()
        session.refresh(actor)
        session.expunge(actor)
    return actor, SpaceContext(space_id="space", space_name="Space", space_role="member", is_global_admin=False)


def update_solution(factory, actor, ctx, mode, setting):
    fields = {"current_phase": "requirements"} if setting == "phase" else {"status": "complete"}
    with factory() as session:
        if mode == "interactive":
            return solution_write.update_solution("solution", SolutionUpdate(**fields), session=session, current_user=actor, space_ctx=ctx)
        if mode == "import":
            csv_data = (
                b"project_name,solution_name,version,current_phase\nProject,Solution,1,requirements\n"
                if setting == "phase" else b"project_name,solution_name,version,status\nProject,Solution,1,complete\n"
            )
            return solution_import.import_solutions(csv_data, session=session, current_user=actor, space_ctx=ctx)
        updated_at = session.get(Solution, "solution").updated_at
        return agent_patch_plan.apply_patch_plan(session, ctx, actor, AgentPatchRequest(
            dry_run=False, reason="Update", idempotency_key="update", operations=[{
                "client_operation_id": "update", "op": "update", "entity": "solution", "id": "solution",
                "if_updated_at": updated_at, "fields": fields,
            }],
        ))


def disable_phase(factory, actor, ctx):
    with factory() as session:
        return phases.set_solution_phases("solution", {"phases": [{"phase_id": "requirements", "is_enabled": False}]}, session=session, current_user=actor, space_ctx=ctx)


def assert_disabled_consistently(factory):
    with factory() as session:
        assert session.get(Solution, "solution").current_phase is None
        assert not session.query(SolutionPhase).filter_by(solution_id="solution", phase_id="requirements").one().is_enabled


@pytest.mark.parametrize("mode", ["interactive", "import", "agent"])
@pytest.mark.parametrize("setting", ["phase", "complete"])
def test_disabling_phase_waits_for_solution_update(db_sessionmaker, monkeypatch, mode, setting):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    checked, release = Event(), Event()
    module = {"interactive": solution_write, "import": solution_import, "agent": agent_patch_plan}[mode]
    attribute = "_validate_current_phase" if setting == "phase" else "_apply_solution_completion_state"
    original = getattr(module, attribute)

    def pause_after_check(*args, **kwargs):
        result = original(*args, **kwargs)
        checked.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(module, attribute, pause_after_check)
    with ThreadPoolExecutor(max_workers=2) as pool:
        update = pool.submit(update_solution, db_sessionmaker, actor, ctx, mode, setting)
        try:
            assert checked.wait(10)
            disable = pool.submit(disable_phase, db_sessionmaker, actor, ctx)
            with pytest.raises(TimeoutError):
                disable.result(timeout=0.25)
        finally:
            release.set()
        result = update.result(timeout=15)
        if mode == "import":
            assert result["updated"] == 1 and not result["errors"]
        if mode == "agent":
            assert result.applied
        disable.result(timeout=15)
    assert_disabled_consistently(db_sessionmaker)


@pytest.mark.parametrize("mode", ["interactive", "import", "agent"])
@pytest.mark.parametrize("setting", ["phase", "complete"])
def test_solution_update_waits_for_phase_disable(db_sessionmaker, monkeypatch, mode, setting):
    if db_sessionmaker.kw["bind"].dialect.name != "sqlite":
        pytest.skip("SQLite concurrency proxy")
    actor, ctx = setup_space(db_sessionmaker)
    checked, release = Event(), Event()
    original = phases._ensure_solution_exists

    def pause_after_check(*args, **kwargs):
        result = original(*args, **kwargs)
        checked.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(phases, "_ensure_solution_exists", pause_after_check)
    with ThreadPoolExecutor(max_workers=2) as pool:
        disable = pool.submit(disable_phase, db_sessionmaker, actor, ctx)
        try:
            assert checked.wait(10)
            update = pool.submit(update_solution, db_sessionmaker, actor, ctx, mode, setting)
            with pytest.raises(TimeoutError):
                update.result(timeout=0.25)
        finally:
            release.set()
        disable.result(timeout=15)
        if setting == "phase" and mode == "interactive":
            with pytest.raises(HTTPException) as exc:
                update.result(timeout=15)
            assert exc.value.status_code == 400
        else:
            result = update.result(timeout=15)
            if mode == "import":
                if setting == "phase":
                    assert result["updated"] == 0 and len(result["errors"]) == 1
                else:
                    assert result["updated"] == 1 and not result["errors"]
            if mode == "agent":
                if setting == "phase":
                    assert not result.valid and result.results[0].code == "CURRENT_PHASE_INVALID"
                else:
                    assert result.applied
    assert_disabled_consistently(db_sessionmaker)


def test_solution_import_rechecks_access_for_existing_projects(db_sessionmaker, monkeypatch):
    actor, ctx = setup_space(db_sessionmaker)
    with db_sessionmaker() as session:
        session.add(Solution(solution_id="other", space_id="space", project_id="project", solution_name="Other", version="1"))
        session.commit()
    original_lock = solution_import.lock_work_space
    calls = 0

    def revoke_before_second_lock(session, space_ctx, user):
        nonlocal calls
        calls += 1
        if calls == 2:
            with db_sessionmaker() as other:
                other.query(SpaceMembership).filter_by(space_id="space", user_id="actor").one().status = "inactive"
                other.commit()
        original_lock(session, space_ctx, user)

    monkeypatch.setattr(solution_import, "lock_work_space", revoke_before_second_lock)
    with db_sessionmaker() as session:
        result = solution_import.import_solutions(
            b"project_name,solution_name,version,description\nProject,Solution,1,First\nProject,Other,1,Second\n",
            session=session, current_user=actor, space_ctx=ctx,
        )
    assert result["updated"] == 1
    assert result["errors"] == ["Row 3: import stopped because access to the space changed"]
    with db_sessionmaker() as session:
        assert session.get(Solution, "solution").description == "First"
        assert session.get(Solution, "other").description != "Second"
