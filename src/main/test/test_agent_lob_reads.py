from datetime import datetime, timezone

import pytest

from backend.app.models import ChangeLog, Program, Space
from backend.app.services.agent_audit import list_agent_audit_feed
from backend.app.services.agent_work_graph import build_work_graph
from backend.app.services.agent_work_items import get_agent_program
from backend.app.services.spaces import SpaceContext


class TextLob:
    def __init__(self, value):
        self._payload = value
        self.reads = 0

    def read(self):
        self.reads += 1
        return self._payload


def test_agent_program_and_audit_reads_handle_database_lobs(db_sessionmaker):
    ctx = SpaceContext(space_id="lob-space", space_name="LOB", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="lob-space", name="LOB", slug="lob-space"),
            Program(program_id="lob-program", space_id="lob-space", program_name="Program", description="initial"),
            ChangeLog(change_id="lob-change", space_id="lob-space", entity_type="project", entity_id="p",
                      action="update", user_id="u", old_value="old", new_value="new",
                      created_at=datetime.now(timezone.utc)),
        ])
        session.commit()
        program = session.get(Program, "lob-program")
        change = session.get(ChangeLog, "lob-change")
        program.description = TextLob("program description")
        change.old_value = TextLob("old description")
        change.new_value = TextLob(b"new description")
        with session.no_autoflush:
            assert get_agent_program(session, "lob-program", ctx).description == "program description"
            assert build_work_graph(session, ctx).programs[0].description == "program description"
            record = list_agent_audit_feed(session, ctx, requester_user_id="u").records[0]
            assert record.old_value == "old description"
            assert record.new_value == "new description"
        session.rollback()


def test_agent_schema_does_not_hide_lob_read_failure():
    from backend.app.schemas.agent import AgentAuditRecordRead

    class BrokenLob:
        def read(self):
            raise OSError("LOB unavailable")

    with pytest.raises(OSError, match="LOB unavailable"):
        AgentAuditRecordRead.model_validate({
            "change_id": "id", "entity_type": "project", "entity_id": "p", "action": "update",
            "user_id": "u", "created_at": datetime.now(timezone.utc), "old_value": BrokenLob(),
        })


def test_agent_proposal_diff_reads_lob_text_without_changing_numeric_values(db_sessionmaker):
    from backend.app.models import Project
    from backend.app.schemas.agent import AgentPatchOperation, AgentPatchRequest
    from backend.app.services.agent_change_requests import build_patch_diff

    ctx = SpaceContext(space_id="diff-space", space_name="Diff", is_global_admin=False, space_role="member")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="diff-space", name="Diff", slug="diff-space"),
            Program(program_id="diff-program", space_id="diff-space", program_name="Program"),
            Project(project_id="diff-project", space_id="diff-space", program_id="diff-program",
                    project_name="Project", description="old", priority=2),
        ])
        session.commit()
        project = session.get(Project, "diff-project")
        project.description = TextLob("old description")
        payload = AgentPatchRequest(operations=[AgentPatchOperation(
            client_operation_id="change", op="update", entity="project", id="diff-project",
            fields={"description": "new description", "priority": 3},
        )])
        with session.no_autoflush:
            diff = build_patch_diff(session, ctx, payload)
        assert diff[0]["fields"]["description"] == {"old": "old description", "new": "new description"}
        assert diff[0]["fields"]["priority"] == {"old": 2, "new": 3}
        session.rollback()


def test_change_request_stored_json_lobs_are_read_and_fail_loudly():
    import json
    from backend.app.models import AgentChangeRequest
    from backend.app.services.agent_change_requests import _row_to_read, _same_idempotent_request

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = AgentChangeRequest(
        change_request_id="request", space_id="space", proposed_by_user_id="user", status="pending",
        reason="reason", idempotency_key="key", created_at=now, updated_at=now,
    )
    row.operations_json = TextLob(json.dumps([{
        "client_operation_id": "op", "op": "create", "entity": "project",
        "fields": {"project_name": "Project"},
    }]))
    row.validation_json = TextLob(json.dumps({
        "valid": True, "applied": False, "dry_run": True, "operation_count": 1, "results": [],
    }))
    row.diff_json = TextLob(json.dumps([{
        "client_operation_id": "op", "op": "create", "entity": "project", "fields": {},
    }]))
    row.review_note = TextLob("review note")
    row.failed_reason = TextLob("failure reason")
    result = _row_to_read(row)
    assert result.operation_count == 1
    assert result.validation.valid is True
    assert result.diff[0].client_operation_id == "op"
    assert result.review_note == "review note"
    assert result.failed_reason == "failure reason"
    assert row.operations_json.reads == 1
    assert row.validation_json.reads == 1
    assert row.diff_json.reads == 1
    assert _same_idempotent_request(row, reason="reason", operations_json=row.operations_json.read())

    class BrokenLob:
        def read(self):
            raise OSError("stored LOB unavailable")

    row.operations_json = BrokenLob()
    with pytest.raises(OSError, match="stored LOB unavailable"):
        _row_to_read(row)
