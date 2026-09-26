from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import oracle

from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("entity", ["program", "project", "solution", "task"])
@pytest.mark.parametrize("operation", ["update", "archive"])
def test_apply_validation_lock_queries_are_valid_for_oracle(
    db_sessionmaker, entity, operation
):
    payload = AgentPatchRequest(
        dry_run=False,
        reason="Validate the target under a row lock",
        idempotency_key="oracle-lock-query",
        operations=[
            {
                "client_operation_id": "target",
                "entity": entity,
                "op": operation,
                "id": "missing-target",
                "if_updated_at": datetime(2026, 1, 1),
                "fields": {f"{entity}_name": "Renamed"}
                if operation == "update"
                else {},
            }
        ],
    )
    space_ctx = SpaceContext(
        space_id="oracle-lock-space",
        space_name="Oracle lock space",
        space_role="member",
        is_global_admin=False,
    )
    statements = []

    def capture_oracle_sql(orm_execute_state):
        statements.append(
            str(
                orm_execute_state.statement.compile(
                    dialect=oracle.dialect(),
                    compile_kwargs={"literal_binds": True},
                )
            ).upper()
        )

    with db_sessionmaker() as session:
        # Inspect the actual statement executed by each validator. SQLite alone
        # would silently accept a limit and ignore FOR UPDATE.
        event.listen(session, "do_orm_execute", capture_oracle_sql)
        response = validate_patch_plan(session, space_ctx, payload, for_apply=True)

    assert response.results[0].code == f"{entity.upper()}_NOT_FOUND"
    assert len(statements) == 1
    sql = statements[0]
    assert "FOR UPDATE" in sql
    assert "FETCH FIRST" not in sql
    assert "FETCH NEXT" not in sql
    assert "ROWNUM" not in sql
    assert "OFFSET" not in sql
