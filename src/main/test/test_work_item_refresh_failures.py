from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from backend.app.models import Program, Project, Solution, Space, User
from backend.app.routes.projects import write as project_write
from backend.app.routes.solutions import write as solution_write
from backend.app.schemas import ProjectCreate, ProjectUpdate, SolutionUpdate
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize(
    "operation", ["project_create", "project_update", "solution_move"]
)
def test_committed_work_item_publishes_even_when_refresh_fails(
    db_sessionmaker, test_user, monkeypatch, operation
):
    space = SpaceContext(
        space_id="refresh-space",
        space_name="Refresh",
        space_role="space_admin",
        is_global_admin=True,
    )
    with db_sessionmaker() as session:
        session.add_all(
            [
                User(user_id=test_user.user_id, soeid=test_user.soeid, email="test-user@fixture.invalid",
                     display_name=test_user.display_name, password_hash="unused", role="global_admin", is_active=True),
                Space(space_id="refresh-space", name="Refresh", slug="refresh"),
                Program(
                    program_id="program",
                    space_id="refresh-space",
                    program_name="Program",
                ),
                Project(
                    project_id="project",
                    space_id="refresh-space",
                    program_id="program",
                    project_name="Before",
                    sponsor="Test User",
                    owner="Test User",
                ),
                Project(
                    project_id="destination",
                    space_id="refresh-space",
                    program_id="program",
                    project_name="Destination",
                    sponsor="Test User",
                    owner="Test User",
                ),
                Solution(
                    solution_id="solution",
                    space_id="refresh-space",
                    project_id="project",
                    solution_name="Solution",
                    version="1",
                    owner="Test User",
                    assignee="Test User",
                ),
            ]
        )
        session.commit()
        events = []
        monkeypatch.setattr(
            project_write,
            "_publish_project_mutation",
            lambda space_id: events.append((space_id, False)),
        )
        monkeypatch.setattr(
            solution_write,
            "_publish_solution_mutation",
            lambda space_id, *, invalidate_tasks=False: events.append(
                (space_id, invalidate_tasks)
            ),
        )
        monkeypatch.setattr(
            session,
            "refresh",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("refresh failed")
            ),
        )
        with pytest.raises((HTTPException, RuntimeError)):
            if operation == "project_create":
                project_write.create_project(
                    ProjectCreate(project_name="Created", program_id="program"),
                    session=session,
                    current_user=test_user,
                    space_ctx=space,
                )
            elif operation == "project_update":
                project_write.update_project(
                    "project",
                    ProjectUpdate(project_name="After"),
                    session=session,
                    current_user=test_user,
                    space_ctx=space,
                )
            else:
                solution_write.update_solution(
                    "solution",
                    SolutionUpdate(project_id="destination"),
                    session=session,
                    current_user=test_user,
                    space_ctx=space,
                )
        assert events == [("refresh-space", operation == "solution_move")]

    with db_sessionmaker() as check:
        if operation == "project_create":
            assert check.query(Project).filter_by(project_name="Created").one()
        elif operation == "project_update":
            assert check.get(Project, "project").project_name == "After"
        else:
            assert check.get(Solution, "solution").project_id == "destination"


@pytest.mark.parametrize("operation", ["create", "update"])
def test_failed_project_commit_keeps_conflict_mapping_and_does_not_publish(
    db_sessionmaker, test_user, monkeypatch, operation
):
    space = SpaceContext(
        space_id="refresh-space",
        space_name="Refresh",
        space_role="space_admin",
        is_global_admin=True,
    )
    with db_sessionmaker() as session:
        session.add_all(
            [
                User(user_id=test_user.user_id, soeid=test_user.soeid, email="test-user@fixture.invalid",
                     display_name=test_user.display_name, password_hash="unused", role="global_admin", is_active=True),
                Space(space_id="refresh-space", name="Refresh", slug="refresh"),
                Program(
                    program_id="program",
                    space_id="refresh-space",
                    program_name="Program",
                ),
                Project(
                    project_id="project",
                    space_id="refresh-space",
                    program_id="program",
                    project_name="Before",
                    sponsor="Test User",
                    owner="Test User",
                ),
            ]
        )
        session.commit()
        events = []
        monkeypatch.setattr(project_write, "_publish_project_mutation", events.append)

        def fail_commit():
            raise IntegrityError(
                "UPDATE projects", {}, Exception("uix_project_space_name")
            )

        monkeypatch.setattr(session, "commit", fail_commit)
        with pytest.raises(HTTPException) as error:
            if operation == "create":
                project_write.create_project(
                    ProjectCreate(project_name="Created", program_id="program"),
                    session=session,
                    current_user=test_user,
                    space_ctx=space,
                )
            else:
                project_write.update_project(
                    "project",
                    ProjectUpdate(project_name="After"),
                    session=session,
                    current_user=test_user,
                    space_ctx=space,
                )
        assert error.value.status_code == 400
        assert error.value.detail == "Project name already exists"
        assert events == []
