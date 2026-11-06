from __future__ import annotations

import pytest
from sqlalchemy.dialects import oracle

from backend.app.models import (
    Program,
    Project,
    Solution,
    Space,
    SpaceMembership,
    Task,
    User,
)
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import apply_patch_plan
from backend.app.services.user_admin_guards import _space_admin_lock_statement
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("move_first", [True, False])
def test_agent_plan_move_and_create_task_keeps_task_in_solution_project(
    db_sessionmaker, move_first
):
    with db_sessionmaker() as session:
        actor = User(
            user_id="actor",
            soeid="actor",
            email="actor@example.com",
            display_name="Actor",
            password_hash="unused",
            role="user",
            is_active=True,
        )
        session.add_all(
            [
                actor,
                Space(space_id="space", name="Space", slug="space"),
                SpaceMembership(
                    space_id="space", user_id="actor", role="member", status="active"
                ),
                Program(program_id="program", space_id="space", program_name="Program"),
                Project(
                    project_id="source",
                    space_id="space",
                    program_id="program",
                    project_name="Source",
                    sponsor="Actor",
                    owner="Actor",
                ),
                Project(
                    project_id="destination",
                    space_id="space",
                    program_id="program",
                    project_name="Destination",
                    sponsor="Actor",
                    owner="Actor",
                ),
                Solution(
                    solution_id="solution",
                    space_id="space",
                    project_id="source",
                    solution_name="Solution",
                    version="1",
                    owner="Actor",
                    assignee="Actor",
                ),
            ]
        )
        session.commit()
        move = {
            "client_operation_id": "move",
            "op": "update",
            "entity": "solution",
            "id": "solution",
            "if_updated_at": session.get(Solution, "solution").updated_at,
            "fields": {"project_id": "destination"},
        }
        create = {
            "client_operation_id": "task",
            "op": "create",
            "entity": "task",
            "solution_id": "solution",
            "fields": {"task_name": "New Task"},
        }
        payload = AgentPatchRequest(
            dry_run=False,
            reason="Move and create",
            idempotency_key="move-create",
            operations=[move, create] if move_first else [create, move],
        )
        ctx = SpaceContext(
            space_id="space",
            space_name="Space",
            space_role="member",
            is_global_admin=False,
        )
        result = apply_patch_plan(session, ctx, actor, payload)
        assert result.valid and result.applied, result
        solution = session.get(Solution, "solution")
        task = (
            session.query(Task)
            .filter_by(solution_id="solution", task_name="New Task")
            .one()
        )
        assert solution.project_id == task.project_id == "destination"


def test_work_space_sentinel_locks_only_space_rows_on_oracle():
    sql = str(
        _space_admin_lock_statement(["space"]).compile(dialect=oracle.dialect())
    ).upper()
    assert "FOR UPDATE" in sql
    assert " JOIN " not in sql
    assert "PROJECT" not in sql
    assert "SOLUTION" not in sql
