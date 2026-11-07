from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.models import Program, Project, Solution, Task, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import apply_patch_plan, validate_patch_plan
from backend.app.services.spaces import SpaceContext
from test_agent_api import _seed_work_graph


@pytest.mark.parametrize("stage", ["validate", "apply"])
@pytest.mark.parametrize("hidden", ["deleted", "other-space"])
@pytest.mark.parametrize("entity", ["project", "solution", "task"])
def test_agent_patch_cannot_mutate_work_under_hidden_program(db_sessionmaker, hidden, entity, stage):
    _, space_id, _, other_space_id, project_id, solution_id, task_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        project = session.get(Project, project_id)
        program = session.get(Program, project.program_id)
        if hidden == "deleted":
            program.deleted_at = datetime.now(timezone.utc)
        else:
            program.program_name = "Historical hidden program"
            program.space_id = other_space_id
        session.commit()
        row = {"project": project, "solution": session.get(Solution, solution_id), "task": session.get(Task, task_id)}[entity]
        entity_id = getattr(row, f"{entity}_id")
        op = {"client_operation_id": "one", "entity": entity, "op": "update", "id": entity_id,
              "if_updated_at": row.updated_at, "fields": {"description": "should not apply"}}
        ctx = SpaceContext(space_id=space_id, space_name="Space", space_role="member", is_global_admin=False)
        request = AgentPatchRequest(dry_run=False, reason="review", idempotency_key="test", operations=[op])
        if stage == "validate":
            validation = validate_patch_plan(session, ctx, request)
            assert not validation.valid, validation.model_dump()
        else:
            actor = session.query(User).filter(User.user_id.like(f"user-{space_id}-%")).one()
            applied = apply_patch_plan(session, ctx, actor, request)
            assert not applied.applied, applied.model_dump()
            session.refresh(row)
            assert row.description != "should not apply"


@pytest.mark.parametrize("hidden", ["deleted", "other-space"])
@pytest.mark.parametrize("entity", ["project", "solution", "task"])
def test_agent_archive_rejects_hidden_program_ancestor(db_sessionmaker, hidden, entity):
    _, space_id, _, other_space_id, project_id, solution_id, task_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        project = session.get(Project, project_id)
        program = session.get(Program, project.program_id)
        if hidden == "deleted":
            program.deleted_at = datetime.now(timezone.utc)
        else:
            program.program_name = "Historical hidden program"
            program.space_id = other_space_id
        session.commit()
        row = {"project": project, "solution": session.get(Solution, solution_id), "task": session.get(Task, task_id)}[entity]
        ctx = SpaceContext(space_id=space_id, space_name="Space", space_role="member", is_global_admin=False)
        payload = AgentPatchRequest(operations=[{"client_operation_id": "archive", "entity": entity, "op": "archive",
                                                  "id": getattr(row, f"{entity}_id"), "if_updated_at": row.updated_at}])
        result = validate_patch_plan(session, ctx, payload)
        assert result.results[0].code == f"{entity.upper()}_NOT_FOUND"


@pytest.mark.parametrize("hidden", ["deleted", "other-space"])
@pytest.mark.parametrize("entity", ["solution", "task"])
def test_agent_create_rejects_parent_under_hidden_program(db_sessionmaker, hidden, entity):
    _, space_id, _, other_space_id, project_id, solution_id, _, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        program = session.get(Program, session.get(Project, project_id).program_id)
        if hidden == "deleted":
            program.deleted_at = datetime.now(timezone.utc)
        else:
            program.program_name = "Historical hidden program"
            program.space_id = other_space_id
        session.commit()
        parent = {"project_id": project_id} if entity == "solution" else {"solution_id": solution_id}
        fields = {"solution_name": "New solution"} if entity == "solution" else {"task_name": "New task"}
        ctx = SpaceContext(space_id=space_id, space_name="Space", space_role="member", is_global_admin=False)
        payload = AgentPatchRequest(operations=[{"client_operation_id": "create", "entity": entity, "op": "create", "fields": fields, **parent}])
        result = validate_patch_plan(session, ctx, payload)
        assert result.results[0].code == ("PROJECT_NOT_FOUND" if entity == "solution" else "SOLUTION_NOT_FOUND")


def test_agent_task_patch_rejects_mismatched_project_parent(db_sessionmaker):
    _, space_id, _, _, project_id, _, task_id, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        task = session.get(Task, task_id)
        original = session.get(Project, project_id)
        other = Project(space_id=space_id, program_id=original.program_id, project_name="Other", sponsor="Sponsor")
        session.add(other)
        session.flush()
        task.project_id = other.project_id
        session.commit()
        ctx = SpaceContext(space_id=space_id, space_name="Space", space_role="member", is_global_admin=False)
        payload = AgentPatchRequest(operations=[{"client_operation_id": "update", "entity": "task", "op": "update", "id": task_id,
                                                  "if_updated_at": task.updated_at, "fields": {"description": "updated"}}])
        result = validate_patch_plan(session, ctx, payload)
        assert result.results[0].code == "TASK_NOT_FOUND"


def test_solution_move_rejects_destination_under_hidden_program(db_sessionmaker):
    _, space_id, _, _, project_id, solution_id, _, *_ = _seed_work_graph(db_sessionmaker)
    with db_sessionmaker() as session:
        hidden_program = Program(space_id=space_id, program_name="Hidden program", deleted_at=datetime.now(timezone.utc))
        session.add(hidden_program)
        session.flush()
        destination = Project(space_id=space_id, program_id=hidden_program.program_id, project_name="Hidden destination", sponsor="Sponsor")
        session.add(destination)
        session.flush()
        solution = session.get(Solution, solution_id)
        ctx = SpaceContext(space_id=space_id, space_name="Space", space_role="member", is_global_admin=False)
        payload = AgentPatchRequest(operations=[{"client_operation_id": "move", "entity": "solution", "op": "update", "id": solution_id,
                                                  "if_updated_at": solution.updated_at, "fields": {"project_id": destination.project_id}}])
        result = validate_patch_plan(session, ctx, payload)
        assert result.results[0].code == "PROJECT_NOT_FOUND"
