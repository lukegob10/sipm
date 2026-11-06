from types import SimpleNamespace

from backend.app.models import Program, Project, Space, User
from backend.app.routes import programs
from backend.app.routes.projects import write as projects
from backend.app.schemas import ProjectUpdate
from backend.app.services.spaces import SpaceContext


def test_project_update_returns_committed_snapshot_if_parents_are_deleted_after_commit(db_sessionmaker, monkeypatch):
    actor = SimpleNamespace(user_id="admin")
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space", name="Space", slug="space"),
            User(user_id="admin", soeid="admin", email="admin@example.com", display_name="Admin", password_hash="unused", role="global_admin", is_active=True),
            Program(program_id="program", space_id="space", program_name="Program"),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
        ])
        session.commit()
    with db_sessionmaker() as session:
        refresh = session.refresh

        def delete_after_refresh(obj, *args, **kwargs):
            refresh(obj, *args, **kwargs)
            with db_sessionmaker() as other:
                projects.delete_project("project", session=other, current_user=actor, space_ctx=ctx)
            with db_sessionmaker() as other:
                programs.delete_program("program", session=other, current_user=actor, space_ctx=ctx)

        monkeypatch.setattr(session, "refresh", delete_after_refresh)
        result = projects.update_project("project", ProjectUpdate(description="Saved"), session=session, current_user=actor, space_ctx=ctx)
        assert result["description"] == "Saved"
        assert result["program_name"] == "Program"
    with db_sessionmaker() as session:
        assert session.get(Project, "project").description == "Saved"
        assert session.get(Program, "program").deleted_at is not None


def test_project_update_can_repair_record_with_archived_program(db_sessionmaker):
    from datetime import datetime, timezone

    actor = SimpleNamespace(user_id="admin")
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space", name="Space", slug="space"),
            User(user_id="admin", soeid="admin", email="admin@example.com", display_name="Admin", password_hash="unused", role="global_admin", is_active=True),
            Program(program_id="program", space_id="space", program_name="Archived", deleted_at=datetime.now(timezone.utc)),
            Project(project_id="project", space_id="space", program_id="program", project_name="Project"),
        ])
        session.commit()
        result = projects.update_project("project", ProjectUpdate(description="Repair"), session=session, current_user=actor, space_ctx=ctx)
        assert result["description"] == "Repair"
        assert result["program_name"] is None


def test_project_create_returns_program_name_at_commit_if_parent_is_archived_afterward(db_sessionmaker, monkeypatch):
    from backend.app.schemas import ProjectCreate

    actor = SimpleNamespace(user_id="admin", display_name="Admin", soeid="admin")
    ctx = SpaceContext(space_id="space", space_name="Space", is_global_admin=True, space_role="space_admin")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space", name="Space", slug="space"),
            User(user_id="admin", soeid="admin", email="admin@example.com", display_name="Admin", password_hash="unused", role="global_admin", is_active=True),
            Program(program_id="program", space_id="space", program_name="Program"),
        ])
        session.commit()
    with db_sessionmaker() as session:
        refresh = session.refresh

        def delete_after_refresh(obj, *args, **kwargs):
            refresh(obj, *args, **kwargs)
            with db_sessionmaker() as other:
                projects.delete_project(obj.project_id, session=other, current_user=actor, space_ctx=ctx)
            with db_sessionmaker() as other:
                programs.delete_program("program", session=other, current_user=actor, space_ctx=ctx)

        monkeypatch.setattr(session, "refresh", delete_after_refresh)
        result = projects.create_project(ProjectCreate(project_name="New", program_id="program"), session=session, current_user=actor, space_ctx=ctx)
        assert result["program_name"] == "Program"
