from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.app.models import Program, Project, Solution, Space, SpaceMembership, Task, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_change_requests import approve_change_request, create_change_request
from backend.app.services.agent_patch_plan import validate_patch_plan
from backend.app.services.spaces import SpaceContext


def _seed(session, *, conflict=False):
    actor = User(
        user_id="move-actor", soeid="moveactor", email="move@example.com", display_name="Move Actor",
        password_hash="unused", role="user", is_active=True,
    )
    session.add_all([
        actor,
        Space(space_id="move-a", name="Move A", slug="move-a"),
        Space(space_id="move-b", name="Move B", slug="move-b"),
        SpaceMembership(space_id="move-a", user_id="move-actor", role="member", status="active"),
        Program(program_id="program-a", space_id="move-a", program_name="Program A"),
        Program(program_id="program-b", space_id="move-b", program_name="Program B"),
        Project(project_id="source", space_id="move-a", program_id="program-a", project_name="Source"),
        Project(project_id="destination", space_id="move-a", program_id="program-a", project_name="Destination"),
        Project(project_id="foreign", space_id="move-b", program_id="program-b", project_name="Foreign"),
        Project(project_id="archived", space_id="move-a", program_id="program-a", project_name="Archived",
                deleted_at=datetime.now(timezone.utc)),
        Solution(solution_id="moving", space_id="move-a", project_id="source", solution_name="Moving", version="1"),
        Task(task_id="child", space_id="move-a", project_id="source", solution_id="moving", task_name="Child"),
    ])
    if conflict:
        session.add(Solution(
            solution_id="conflict", space_id="move-a", project_id="destination",
            solution_name="Moving", version="1",
        ))
    session.commit()
    return actor, SpaceContext(space_id="move-a", space_name="Move A", is_global_admin=False, space_role="member")


def _patch(session, project_id):
    moving = session.get(Solution, "moving")
    return AgentPatchRequest(
        dry_run=False, reason="Move solution", idempotency_key="move-solution",
        operations=[{
            "client_operation_id": "move", "op": "update", "entity": "solution", "id": "moving",
            "if_updated_at": moving.updated_at, "fields": {"project_id": project_id},
        }],
    )


@pytest.mark.parametrize("target", ["foreign", "missing", "archived", "", None])
def test_solution_move_rejects_unavailable_or_cross_space_project(db_sessionmaker, target):
    with db_sessionmaker() as session:
        _actor, ctx = _seed(session)
        validation = validate_patch_plan(session, ctx, _patch(session, target))
        assert validation.valid is False
        assert validation.results[0].code in {"PROJECT_NOT_FOUND", "PROJECT_ID_REQUIRED"}
        assert session.get(Solution, "moving").project_id == "source"


def test_solution_move_checks_name_and_version_in_destination(db_sessionmaker):
    with db_sessionmaker() as session:
        _actor, ctx = _seed(session, conflict=True)
        validation = validate_patch_plan(session, ctx, _patch(session, "destination"))
        assert validation.valid is False
        assert validation.results[0].code == "SOLUTION_CONFLICT"


@pytest.mark.parametrize(
    "field, expected_code", [("solution_name", "SOLUTION_NAME_REQUIRED"), ("version", "VERSION_REQUIRED")],
)
@pytest.mark.parametrize("value", [None, "", "   "])
def test_solution_move_rejects_blank_name_or_version(db_sessionmaker, field, expected_code, value):
    with db_sessionmaker() as session:
        _actor, ctx = _seed(session)
        patch = _patch(session, "destination")
        patch.operations[0].fields[field] = value
        validation = validate_patch_plan(session, ctx, patch)
        assert validation.valid is False
        assert validation.results[0].code == expected_code


def test_approved_same_space_solution_move_updates_child_tasks(db_sessionmaker):
    with db_sessionmaker() as session:
        actor, ctx = _seed(session)
        request = create_change_request(session, ctx, actor, _patch(session, " destination "))
        approved = approve_change_request(session, ctx, actor, request.change_request_id, if_request_fingerprint=request.content_fingerprint)
        assert approved.status == "approved"
        assert session.get(Solution, "moving").project_id == "destination"
        assert session.get(Task, "child").project_id == "destination"


def test_approval_rechecks_destination_after_submission(db_sessionmaker):
    with db_sessionmaker() as session:
        actor, ctx = _seed(session)
        request = create_change_request(session, ctx, actor, _patch(session, "destination"))
        session.get(Project, "destination").deleted_at = datetime.now(timezone.utc)
        session.commit()
        rejected = approve_change_request(session, ctx, actor, request.change_request_id, if_request_fingerprint=request.content_fingerprint)
        assert rejected.status == "failed"
        assert rejected.validation.results[0].code == "PROJECT_NOT_FOUND"
        assert session.get(Solution, "moving").project_id == "source"
        assert session.get(Task, "child").project_id == "source"
