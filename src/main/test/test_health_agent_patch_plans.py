from __future__ import annotations

import pytest
from sqlalchemy.orm.attributes import set_committed_value

from backend.app.models import Program, Project, Solution, Space, Task
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_patch_plan import validate_patch_plan
from backend.app.services.spaces import SpaceContext


class TextLob:
    def __init__(self, value):
        self._payload = value
        self.reads = 0

    def read(self):
        self.reads += 1
        return self._payload


def _seed_patch_rows(session):
    rows = {
        "program": Program(program_id="program", space_id="patch-text", program_name="Program"),
        "project": Project(project_id="project", space_id="patch-text", program_id="program", project_name="Project"),
        "solution": Solution(solution_id="solution", space_id="patch-text", project_id="project", solution_name="Solution"),
        "task": Task(task_id="task", space_id="patch-text", project_id="project", solution_id="solution", task_name="Task"),
    }
    session.add(Space(space_id="patch-text", name="Patch text", slug="patch-text"))
    session.add_all(rows.values())
    session.commit()
    return rows


@pytest.mark.parametrize("entity", ["program", "project", "solution", "task"])
@pytest.mark.parametrize("representation", ["lob", "binary_lob", "bytes"])
def test_patch_text_noops_compare_loaded_values(db_sessionmaker, entity, representation):
    ctx = SpaceContext(space_id="patch-text", space_name="Patch text", space_role="member", is_global_admin=False)
    with db_sessionmaker() as session:
        row = _seed_patch_rows(session)[entity]
        updated_at = row.updated_at
        text = "  déjà vérifié  "
        value = text if representation == "lob" else text.encode("utf-8")
        stored = value if representation == "bytes" else TextLob(value)
        column = "done_criteria" if entity == "task" else "description"
        field = "acceptance_criteria" if entity == "task" else column
        # Model the value returned by an Oracle text column without flushing
        # a synthetic LOB through the SQLite test driver.
        set_committed_value(row, column, stored)
        payload = AgentPatchRequest(operations=[{
            "client_operation_id": "text", "entity": entity, "op": "update",
            "id": getattr(row, f"{entity}_id"), "if_updated_at": updated_at,
            "fields": {field: text},
        }])

        unchanged = validate_patch_plan(session, ctx, payload)
        assert unchanged.valid is False
        assert unchanged.results[0].code == "NO_CHANGES"
        assert row.updated_at == updated_at
        assert getattr(row, column) is stored

        payload.operations[0].fields[field] = "Changed text"
        changed = validate_patch_plan(session, ctx, payload)
        assert changed.valid is True
        assert changed.applied is False
        assert row.updated_at == updated_at
        if isinstance(stored, TextLob):
            assert stored.reads == 2


def test_patch_text_read_failure_propagates(db_sessionmaker):
    class BrokenLob:
        def read(self):
            raise OSError("Text is unavailable")

    ctx = SpaceContext(space_id="patch-text", space_name="Patch text", space_role="member", is_global_admin=False)
    with db_sessionmaker() as session:
        program = _seed_patch_rows(session)["program"]
        payload = AgentPatchRequest(operations=[{
            "client_operation_id": "text", "entity": "program", "op": "update",
            "id": program.program_id, "if_updated_at": program.updated_at,
            "fields": {"description": ""},
        }])
        set_committed_value(program, "description", BrokenLob())
        with pytest.raises(OSError, match="Text is unavailable"):
            validate_patch_plan(session, ctx, payload)
