from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import event
from sqlalchemy.dialects import oracle

from backend.app.models import ChangeLog, Program, Project, Solution, Space, Task, User
from backend.app.schemas.agent import AgentPatchRequest
from backend.app.services.agent_change_requests import (
    approve_change_request,
    create_change_request,
)
from backend.app.services.agent_patch_plan import apply_patch_plan, validate_patch_plan
from backend.app.services.spaces import SpaceContext
from backend.app.services.work_item_names import deleted_work_item_name


MODELS = {"program": Program, "project": Project, "solution": Solution, "task": Task}


@pytest.fixture
def name_reuse_context(db_sessionmaker):
    with db_sessionmaker() as session:
        space = Space(space_id="name-reuse", name="Name Reuse", slug="name-reuse")
        actor = User(
            user_id="name-reviewer",
            soeid="name-reviewer",
            email="name-reviewer@example.com",
            display_name="Name Reviewer",
            password_hash="unused",
            role="global_admin",
        )
        session.add_all([space, actor])
        session.flush()
        program = Program(space_id=space.space_id, program_name="Parent program")
        session.add(program)
        session.flush()
        project = Project(
            space_id=space.space_id,
            program_id=program.program_id,
            project_name="Parent project",
        )
        session.add(project)
        session.flush()
        solution = Solution(
            space_id=space.space_id,
            project_id=project.project_id,
            solution_name="Parent solution",
        )
        session.add(solution)
        session.commit()
        context = SpaceContext(
            space_id=space.space_id,
            space_name=space.name,
            space_role="space_admin",
            is_global_admin=True,
        )
        yield session, context, actor, program, project, solution


def _create_operation(entity, program, project, solution, *, name="Reusable"):
    operation = {
        "client_operation_id": "create",
        "op": "create",
        "entity": entity,
        "fields": {f"{entity}_name": name},
    }
    if entity == "project":
        operation["fields"]["program_id"] = program.program_id
    elif entity == "solution":
        operation["project_id"] = project.project_id
        operation["fields"]["version"] = "1.0.0"
    elif entity == "task":
        operation["solution_id"] = solution.solution_id
    return operation


def _patch(*operations, key="name-reuse"):
    return AgentPatchRequest(
        dry_run=False,
        reason="Reuse a deleted work item's name",
        idempotency_key=key,
        operations=list(operations),
    )


def _create_row(session, context, actor, operation):
    result = apply_patch_plan(session, context, actor, _patch(operation))
    assert result.applied, result.model_dump()
    return session.get(MODELS[operation["entity"]], result.results[0].entity_id)


def _approve(session, context, actor, payload):
    request = create_change_request(session, context, actor, payload)
    assert request.status == "pending"
    return approve_change_request(session, context, actor, request.change_request_id)


@pytest.mark.parametrize("entity", MODELS)
def test_agent_archive_then_create_reuses_name(name_reuse_context, entity):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation(entity, program, project, solution)
    old = _create_row(session, context, actor, operation)
    assert not validate_patch_plan(session, context, _patch(operation)).valid
    old_id = getattr(old, f"{entity}_id")
    archive = _approve(
        session,
        context,
        actor,
        _patch(
            {
                "client_operation_id": "archive",
                "op": "archive",
                "entity": entity,
                "id": old_id,
                "if_updated_at": old.updated_at,
            },
            key="archive",
        ),
    )
    assert archive.status == "approved"
    session.refresh(old)
    assert old.deleted_at is not None
    assert getattr(old, f"{entity}_name") != "Reusable"
    assert len(getattr(old, f"{entity}_name")) <= 255
    replacement = _approve(session, context, actor, _patch(operation, key="replacement"))
    assert replacement.status == "approved", replacement.model_dump()
    replacement_id = replacement.validation.results[0].entity_id
    assert replacement_id != old_id
    assert session.get(MODELS[entity], replacement_id).deleted_at is None
    assert session.query(ChangeLog).filter_by(
        entity_type=entity, entity_id=old_id, field=f"{entity}_name", action="delete"
    ).count() == 1


@pytest.mark.parametrize("entity", MODELS)
@pytest.mark.parametrize("mode", ["create", "rename"])
def test_agent_reclaims_legacy_deleted_names_only_during_application(
    name_reuse_context, entity, mode
):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation(entity, program, project, solution)
    old = _create_row(session, context, actor, operation)
    old.deleted_at = datetime.now(timezone.utc)
    session.commit()
    if mode == "rename":
        live = _create_row(
            session, context, actor,
            _create_operation(entity, program, project, solution, name="Live item"),
        )
        operation = {
            "client_operation_id": "rename",
            "op": "update",
            "entity": entity,
            "id": getattr(live, f"{entity}_id"),
            "if_updated_at": live.updated_at,
            "fields": {f"{entity}_name": "Reusable"},
        }
    payload = _patch(operation, key="replacement")
    assert validate_patch_plan(session, context, payload).valid
    assert getattr(old, f"{entity}_name") == "Reusable"
    request = create_change_request(session, context, actor, payload)
    session.refresh(old)
    assert getattr(old, f"{entity}_name") == "Reusable"
    result = approve_change_request(session, context, actor, request.change_request_id)
    assert result.status == "approved", result.model_dump()
    session.refresh(old)
    assert old.deleted_at is not None
    assert getattr(old, f"{entity}_name") != "Reusable"
    replacement = session.get(MODELS[entity], result.validation.results[0].entity_id)
    assert getattr(replacement, f"{entity}_name") == "Reusable"
    assert replacement.deleted_at is None
    assert session.query(ChangeLog).filter_by(
        entity_type=entity,
        entity_id=getattr(old, f"{entity}_id"),
        action="update",
        field=f"{entity}_name",
    ).count() == 1


@pytest.mark.parametrize("entity", MODELS)
def test_failed_patch_rolls_back_legacy_name_reclamation(name_reuse_context, entity):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation(entity, program, project, solution)
    old = _create_row(session, context, actor, operation)
    old.deleted_at = datetime.now(timezone.utc)
    session.commit()
    duplicate = {**operation, "client_operation_id": "second-create"}
    result = _approve(
        session, context, actor, _patch(operation, duplicate, key="duplicate-patch")
    )
    assert result.status == "failed"
    assert result.validation.results[0].code == "APPLY_FAILED"
    assert result.validation.results[0].client_operation_id == "second-create"
    assert result.validation.results[0].message == "Patch application failed due to a data conflict"
    session.refresh(old)
    assert getattr(old, f"{entity}_name") == "Reusable"
    assert old.deleted_at is not None
    model = MODELS[entity]
    assert session.query(model).filter(
        getattr(model, f"{entity}_name") == "Reusable", model.deleted_at.is_(None)
    ).count() == 0
    assert session.query(ChangeLog).filter_by(
        entity_type=entity,
        entity_id=getattr(old, f"{entity}_id"),
        field=f"{entity}_name",
        action="update",
    ).count() == 0


@pytest.mark.parametrize("entity", MODELS)
def test_legacy_name_reclamation_is_space_scoped(name_reuse_context, entity):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation(entity, program, project, solution)
    old = _create_row(session, context, actor, operation)
    old.deleted_at = datetime.now(timezone.utc)
    other_space = Space(space_id="other-space", name="Other Space", slug="other-space")
    other_program = Program(space_id=other_space.space_id, program_name="Other program")
    session.add_all([other_space, other_program])
    session.flush()
    other_project = Project(
        space_id=other_space.space_id,
        program_id=other_program.program_id,
        project_name="Other project",
    )
    session.add(other_project)
    session.flush()
    other_solution = Solution(
        space_id=other_space.space_id,
        project_id=other_project.project_id,
        solution_name="Other solution",
    )
    session.add(other_solution)
    session.commit()
    other_context = SpaceContext(
        space_id=other_space.space_id,
        space_name=other_space.name,
        space_role="space_admin",
        is_global_admin=True,
    )
    other = _create_row(
        session, other_context, actor,
        _create_operation(entity, other_program, other_project, other_solution),
    )
    other.deleted_at = datetime.now(timezone.utc)
    session.commit()
    result = apply_patch_plan(session, context, actor, _patch(operation))
    assert result.applied, result.model_dump()
    session.refresh(other)
    assert getattr(other, f"{entity}_name") == "Reusable"
    assert other.deleted_at is not None


@pytest.mark.parametrize("entity", ["solution", "task"])
def test_legacy_name_reclamation_is_parent_scoped(name_reuse_context, entity):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation(entity, program, project, solution)
    old = _create_row(session, context, actor, operation)
    old.deleted_at = datetime.now(timezone.utc)
    other_project = Project(
        space_id=context.space_id,
        program_id=program.program_id,
        project_name="Other project",
    )
    session.add(other_project)
    session.flush()
    other_solution = Solution(
        space_id=context.space_id,
        project_id=other_project.project_id,
        solution_name="Other solution",
    )
    session.add(other_solution)
    session.commit()
    other = _create_row(
        session, context, actor,
        _create_operation(entity, program, other_project, other_solution),
    )
    other.deleted_at = datetime.now(timezone.utc)
    session.commit()
    assert apply_patch_plan(session, context, actor, _patch(operation)).applied
    session.refresh(other)
    assert getattr(other, f"{entity}_name") == "Reusable"


def test_solution_version_change_reclaims_only_matching_deleted_version(name_reuse_context):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation("solution", program, project, solution)
    old = _create_row(session, context, actor, operation)
    old.deleted_at = datetime.now(timezone.utc)
    session.commit()
    other = _create_row(
        session, context, actor,
        {**operation, "fields": {"solution_name": "Reusable", "version": "2.0.0"}},
    )
    other.deleted_at = datetime.now(timezone.utc)
    session.commit()
    live = _create_row(
        session, context, actor,
        {**operation, "fields": {"solution_name": "Reusable", "version": "3.0.0"}},
    )
    result = _approve(
        session, context, actor,
        _patch({
            "client_operation_id": "version-change",
            "entity": "solution",
            "op": "update",
            "id": live.solution_id,
            "if_updated_at": live.updated_at,
            "fields": {"version": "1.0.0"},
        }, key="version-change"),
    )
    assert result.status == "approved", result.model_dump()
    session.refresh(old)
    session.refresh(other)
    assert old.solution_name != "Reusable"
    assert other.solution_name == "Reusable"
    assert live.version == "1.0.0"


def test_deleted_names_fit_column_and_use_full_id_to_avoid_truncation_collisions():
    deleted_at = datetime(2026, 9, 30, tzinfo=timezone.utc)
    first_id = "12345678-1234-1234-1234-123456789012"
    second_id = "12345678-1234-1234-1234-123456789013"
    first = deleted_work_item_name("A" * 255, first_id, deleted_at)
    second = deleted_work_item_name("A" * 254 + "B", second_id, deleted_at)
    assert len(first) == len(second) == 255
    assert first != second
    assert first_id in first
    assert second_id in second


def test_legacy_name_lock_query_is_valid_for_oracle(name_reuse_context):
    session, context, actor, program, project, solution = name_reuse_context
    operation = _create_operation("task", program, project, solution)
    old = _create_row(session, context, actor, operation)
    old.deleted_at = datetime.now(timezone.utc)
    session.commit()
    statements = []

    def capture_sql(orm_execute_state):
        sql = str(orm_execute_state.statement.compile(dialect=oracle.dialect())).upper()
        if "FOR UPDATE" in sql:
            statements.append(sql)

    event.listen(session, "do_orm_execute", capture_sql)
    try:
        assert apply_patch_plan(session, context, actor, _patch(operation)).applied
    finally:
        event.remove(session, "do_orm_execute", capture_sql)
    assert len(statements) == 1
    assert all(marker not in statements[0] for marker in ("FETCH FIRST", "FETCH NEXT", "ROWNUM", "OFFSET"))


@pytest.mark.anyio
async def test_regular_program_delete_releases_name(client, db_sessionmaker):
    created = await client.post(
        "/project-manager/api/programs/", json={"program_name": "Reusable program"}
    )
    assert created.status_code == 201, created.text
    original_id = created.json()["program_id"]
    deleted = await client.delete(f"/project-manager/api/programs/{original_id}")
    assert deleted.status_code == 204, deleted.text
    recreated = await client.post(
        "/project-manager/api/programs/", json={"program_name": "Reusable program"}
    )
    assert recreated.status_code == 201, recreated.text
    assert recreated.json()["program_id"] != original_id
    with db_sessionmaker() as session:
        old = session.get(Program, original_id)
        assert old.deleted_at is not None
        assert old.program_name != "Reusable program"


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["create", "rename"])
async def test_regular_program_reclaims_legacy_deleted_name(client, db_sessionmaker, mode):
    created = await client.post(
        "/project-manager/api/programs/", json={"program_name": "Legacy program"}
    )
    assert created.status_code == 201, created.text
    with db_sessionmaker() as session:
        old = session.get(Program, created.json()["program_id"])
        old.deleted_at = datetime.now(timezone.utc)
        session.commit()
    if mode == "create":
        result = await client.post(
            "/project-manager/api/programs/", json={"program_name": "Legacy program"}
        )
        assert result.status_code == 201, result.text
    else:
        live = await client.post(
            "/project-manager/api/programs/", json={"program_name": "Live program"}
        )
        assert live.status_code == 201, live.text
        result = await client.patch(
            f"/project-manager/api/programs/{live.json()['program_id']}",
            json={"program_name": "Legacy program"},
        )
        assert result.status_code == 200, result.text
    assert result.json()["program_name"] == "Legacy program"
