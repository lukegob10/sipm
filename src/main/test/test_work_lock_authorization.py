from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import event
from sqlalchemy.dialects import oracle

from backend.app.models import (
    AgentChangeRequest,
    Program,
    Project,
    Solution,
    Space,
    SpaceMembership,
    Task,
    User,
)
from backend.app.routes.solutions.write import update_solution
from backend.app.routes.agent.change_requests import delegated_approve_agent_change_request
from backend.app.routes.tasks import import_export as task_import
from backend.app.routes.tasks.import_export import import_tasks
from backend.app.routes.tasks.write import create_task
from backend.app.schemas import SolutionUpdate, TaskCreate
from backend.app.schemas.agent import AgentDelegatedChangeRequestReview, AgentPatchRequest
from backend.app.services.agent_change_requests import (
    approve_change_request,
    approve_change_request_operations,
    create_change_request,
)
from backend.app.services.agent_patch_plan import validate_patch_plan
from backend.app.services.spaces import SpaceContext
from backend.app.services import work_items


def _setup(session):
    reviewer = User(
        user_id="reviewer",
        soeid="reviewer",
        email="reviewer@example.com",
        display_name="Reviewer",
        password_hash="unused",
        role="user",
        is_active=True,
    )
    proposer = User(
        user_id="proposer",
        soeid="proposer",
        email="proposer@example.com",
        display_name="Proposer",
        password_hash="unused",
        role="user",
        is_active=True,
    )
    session.add_all(
        [
            reviewer,
            proposer,
            Space(space_id="guard-space", name="Guard", slug="guard-space"),
            SpaceMembership(
                space_id="guard-space",
                user_id="reviewer",
                role="member",
                status="active",
            ),
            SpaceMembership(
                space_id="guard-space",
                user_id="proposer",
                role="member",
                status="active",
            ),
            Program(
                program_id="program", space_id="guard-space", program_name="Program"
            ),
            Project(
                project_id="source",
                space_id="guard-space",
                program_id="program",
                project_name="Source",
                sponsor="Reviewer",
                owner="Reviewer",
            ),
            Project(
                project_id="destination",
                space_id="guard-space",
                program_id="program",
                project_name="Destination",
                sponsor="Reviewer",
                owner="Reviewer",
            ),
            Solution(
                solution_id="solution",
                space_id="guard-space",
                project_id="source",
                solution_name="Solution",
                version="1",
                owner="Reviewer",
                assignee="Reviewer",
            ),
        ]
    )
    session.commit()
    return (
        reviewer,
        proposer,
        SpaceContext(
            space_id="guard-space",
            space_name="Guard",
            is_global_admin=False,
            space_role="member",
        ),
    )


@pytest.mark.parametrize("operation", ["task", "move", "csv", "approve", "partial", "delegated"])
def test_revoked_membership_while_waiting_rejects_write(
    db_sessionmaker, monkeypatch, operation
):
    with db_sessionmaker() as session:
        actor, proposer, ctx = _setup(session)
        request_id = None
        if operation in {"approve", "partial", "delegated"}:
            project = session.get(Project, "source")
            patch = AgentPatchRequest(
                dry_run=False,
                reason="Update project",
                idempotency_key="guard",
                operations=[
                    {
                        "client_operation_id": "change",
                        "op": "update",
                        "entity": "project",
                        "id": "source",
                        "if_updated_at": project.updated_at,
                        "fields": {"project_name": "Changed"},
                    }
                ],
            )
            request_id = create_change_request(
                session, ctx, proposer, patch
            ).change_request_id

        original_lock = work_items.lock_space_admin_spaces

        def revoke_before_lock(db, ids):
            with db_sessionmaker() as concurrent:
                membership = (
                    concurrent.query(SpaceMembership)
                    .filter_by(space_id="guard-space", user_id="reviewer")
                    .one()
                )
                membership.status = "inactive"
                concurrent.commit()
            return original_lock(db, ids)

        monkeypatch.setattr(work_items, "lock_space_admin_spaces", revoke_before_lock)
        with pytest.raises(HTTPException) as error:
            if operation == "task":
                create_task(
                    "solution",
                    TaskCreate(task_name="New"),
                    session=session,
                    current_user=actor,
                    space_ctx=ctx,
                )
            elif operation == "move":
                update_solution(
                    "solution",
                    SolutionUpdate(project_id="destination"),
                    session=session,
                    current_user=actor,
                    space_ctx=ctx,
                )
            elif operation == "csv":
                import_tasks(
                    b"project_name,solution_name,version,task_name\nSource,Solution,1,New\n",
                    session=session,
                    current_user=actor,
                    space_ctx=ctx,
                )
            elif operation == "approve":
                from backend.app.services.agent_change_requests import _content_fingerprint
                request = session.get(AgentChangeRequest, request_id)
                approve_change_request(session, ctx, actor, request_id, if_request_fingerprint=_content_fingerprint(request))
            elif operation == "partial":
                from backend.app.services.agent_change_requests import _content_fingerprint
                approve_change_request_operations(
                    session, ctx, actor, request_id, ["change"],
                    if_request_fingerprint=_content_fingerprint(session.get(AgentChangeRequest, request_id)),
                )
            else:
                request = session.get(AgentChangeRequest, request_id)
                from backend.app.services.agent_change_requests import _content_fingerprint
                delegated_approve_agent_change_request(
                    request_id,
                    AgentDelegatedChangeRequestReview(
                        confirm_change_request_id=request_id,
                        if_request_updated_at=request.updated_at,
                        if_request_fingerprint=_content_fingerprint(request),
                    ),
                    session=session, current_user=actor, space_ctx=ctx,
                )
        assert error.value.status_code == 403
        session.rollback()
        with db_sessionmaker() as check:
            assert check.get(Solution, "solution").project_id == "source"
            assert check.query(Task).count() == 0
            assert check.get(Project, "source").project_name == "Source"
            if request_id:
                assert check.get(AgentChangeRequest, request_id).status == "pending"


@pytest.mark.parametrize(
    "condition",
    ["missing", "inactive", "deactivated", "personal_nonowner", "new_global"],
)
def test_work_guard_requires_current_membership_for_initial_member(
    db_sessionmaker, condition
):
    with db_sessionmaker() as session:
        actor, _, ctx = _setup(session)
        membership = (
            session.query(SpaceMembership)
            .filter_by(space_id=ctx.space_id, user_id=actor.user_id)
            .one()
        )
        if condition == "missing":
            session.delete(membership)
        elif condition == "inactive":
            membership.status = "inactive"
        elif condition == "deactivated":
            actor.is_active = False
        elif condition == "personal_nonowner":
            space = session.get(Space, ctx.space_id)
            space.space_kind = "personal"
            space.owner_user_id = "proposer"
        else:
            actor.role = "global_admin"
            session.delete(membership)
        session.commit()
        with pytest.raises(HTTPException) as error:
            work_items.lock_work_space(session, ctx, actor)
        assert error.value.status_code == 403


def test_csv_stops_reports_and_publishes_previously_committed_rows(
    db_sessionmaker, monkeypatch
):
    with db_sessionmaker() as session:
        actor, _, ctx = _setup(session)
        original_lock = work_items.lock_space_admin_spaces
        lock_count = 0
        published = []

        def revoke_before_second_lock(db, ids):
            nonlocal lock_count
            lock_count += 1
            if lock_count == 2:
                with db_sessionmaker() as concurrent:
                    member = (
                        concurrent.query(SpaceMembership)
                        .filter_by(space_id=ctx.space_id, user_id=actor.user_id)
                        .one()
                    )
                    member.status = "inactive"
                    concurrent.commit()
            return original_lock(db, ids)

        monkeypatch.setattr(
            work_items, "lock_space_admin_spaces", revoke_before_second_lock
        )
        monkeypatch.setattr(
            task_import,
            "_publish_task_import",
            lambda space_id, **counts: published.append((space_id, counts)),
        )
        result = import_tasks(
            b"project_name,solution_name,version,task_name\nSource,Solution,1,First\nSource,Solution,1,Second\n",
            session=session,
            current_user=actor,
            space_ctx=ctx,
        )
        assert result["created"] == 1
        assert result["updated"] == 0
        assert result["total_rows"] == 2
        assert result["errors"] == [
            "Row 3: import stopped because access to the space changed"
        ]
        assert published == [
            (ctx.space_id, {"projects_created": 0, "solutions_created": 0})
        ]
        with db_sessionmaker() as check:
            assert [task.task_name for task in check.query(Task).all()] == ["First"]


def test_global_demotion_is_rechecked_after_global_lock(db_sessionmaker, monkeypatch):
    with db_sessionmaker() as session:
        actor, _, ctx = _setup(session)
        actor.role = "global_admin"
        session.commit()
        ctx = SpaceContext(
            space_id=ctx.space_id,
            space_name=ctx.space_name,
            is_global_admin=True,
            space_role="space_admin",
        )
        calls = []
        original_global = work_items.lock_global_admin_users
        original_space = work_items.lock_space_admin_spaces

        def demote_before_lock(db):
            calls.append("global")
            with db_sessionmaker() as concurrent:
                concurrent.get(User, "reviewer").role = "user"
                concurrent.query(SpaceMembership).filter_by(
                    space_id="guard-space", user_id="reviewer"
                ).one().status = "inactive"
                concurrent.commit()
            return original_global(db)

        def mark_space(db, ids):
            calls.append("space")
            return original_space(db, ids)

        monkeypatch.setattr(work_items, "lock_global_admin_users", demote_before_lock)
        monkeypatch.setattr(work_items, "lock_space_admin_spaces", mark_space)
        with pytest.raises(HTTPException) as error:
            work_items.lock_work_space(session, ctx, actor)
        assert error.value.status_code == 403
        assert calls == ["global", "space"]


@pytest.mark.parametrize("is_global", [False, True])
def test_lobby_is_rechecked_under_lock(db_sessionmaker, is_global):
    with db_sessionmaker() as session:
        actor, _, ctx = _setup(session)
        if is_global:
            actor.role = "global_admin"
        session.get(Space, ctx.space_id).space_kind = "lobby"
        session.commit()
        ctx = SpaceContext(
            space_id=ctx.space_id,
            space_name=ctx.space_name,
            is_global_admin=is_global,
            space_role="space_admin" if is_global else "member",
        )
        with pytest.raises(HTTPException) as error:
            work_items.lock_work_space(session, ctx, actor)
        assert error.value.status_code == 400
        assert error.value.headers["X-Error-Code"] == "LOBBY_SPACE_READ_ONLY"


def test_invalid_dry_run_apply_validation_does_not_lock_work_rows(db_sessionmaker):
    with db_sessionmaker() as session:
        _, _, ctx = _setup(session)
        project = session.get(Project, "source")
        payload = AgentPatchRequest(
            dry_run=True,
            reason="Dry run",
            idempotency_key="dry",
            operations=[
                {
                    "client_operation_id": "change",
                    "op": "update",
                    "entity": "project",
                    "id": "source",
                    "if_updated_at": project.updated_at,
                    "fields": {"project_name": "Changed"},
                }
            ],
        )
        sql = []
        event.listen(
            session,
            "do_orm_execute",
            lambda state: sql.append(
                str(state.statement.compile(dialect=oracle.dialect())).upper()
            ),
        )
        result = validate_patch_plan(session, ctx, payload, for_apply=True)
        assert result.valid is False
        assert result.results[0].code == "DRY_RUN_FALSE_REQUIRED"
        assert all("FOR UPDATE" not in statement for statement in sql)
