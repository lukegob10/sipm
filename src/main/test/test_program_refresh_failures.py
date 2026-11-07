from types import SimpleNamespace

import pytest

from backend.app.models import Program, Space, User
from backend.app.routes import programs
from backend.app.schemas import ProgramCreate, ProgramUpdate
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("mode", ["create", "update"])
def test_program_write_publishes_when_post_commit_refresh_fails(db_sessionmaker, monkeypatch, mode):
    ctx = SpaceContext(space_id="space", space_name="Space", space_role="space_admin", is_global_admin=True)
    actor = SimpleNamespace(user_id="admin")
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="space", name="Space", slug="space"),
            User(user_id="admin", soeid="admin", email="admin@example.com", display_name="Admin", password_hash="unused", role="global_admin", is_active=True),
            Program(program_id="program", space_id="space", program_name="Before"),
        ])
        session.commit()
        publications = []
        monkeypatch.setattr(programs, "_publish_program_mutation", lambda space_id, **kw: publications.append((space_id, kw)))
        monkeypatch.setattr(session, "refresh", lambda *_args, **_kw: (_ for _ in ()).throw(RuntimeError("refresh failed")))
        with pytest.raises(RuntimeError, match="refresh failed"):
            if mode == "create":
                programs.create_program(ProgramCreate(program_name="New"), session=session, current_user=actor, space_ctx=ctx)
            else:
                programs.update_program("program", ProgramUpdate(program_name="Updated"), session=session, current_user=actor, space_ctx=ctx)
        assert publications == [("space", {} if mode == "create" else {"include_projects": True})]
    with db_sessionmaker() as session:
        assert session.query(Program).filter_by(program_name="New" if mode == "create" else "Updated").count() == 1
