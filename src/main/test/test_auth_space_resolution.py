from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from backend.app.models import Space
from backend.app.services.spaces import resolve_active_space_context


def test_selected_admin_space_does_not_repeat_default_lobby_lookup(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            Space(space_id="home", name="Home", slug="home", space_kind="lobby"),
            Space(space_id="selected", name="Selected", slug="selected"),
        ])
        session.commit()

    with db_sessionmaker() as session:
        statements = []

        def capture(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement)

        event.listen(session.get_bind(), "before_cursor_execute", capture)
        try:
            ctx = resolve_active_space_context(
                session,
                SimpleNamespace(user_id="admin", role="global_admin"),
                requested_space_id="selected",
            )
        finally:
            event.remove(session.get_bind(), "before_cursor_execute", capture)

        assert ctx.space_id == "selected"
        assert ctx.space_name == "Selected"
        assert ctx.is_global_admin is True
        assert ctx.space_role == "space_admin"
        assert len(statements) == 1


@pytest.mark.parametrize("requested_space_id", [None, "missing", "archived", "deleted", "home"])
def test_admin_space_fallback_still_repairs_lobby(db_sessionmaker, requested_space_id):
    with db_sessionmaker() as session:
        session.add_all([
            Space(
                space_id="home", name="Old Lobby", slug="home",
                space_kind="collaboration", is_active=False, deleted_at=datetime(2025, 1, 1),
            ),
            Space(space_id="archived", name="Archived", slug="archived", is_active=False),
            Space(
                space_id="deleted", name="Deleted", slug="deleted",
                deleted_at=datetime(2025, 1, 1),
            ),
        ])
        session.commit()

        ctx = resolve_active_space_context(
            session,
            SimpleNamespace(user_id="admin", role="global_admin"),
            requested_space_id=requested_space_id,
        )

        assert ctx.space_id == "home"
        assert ctx.space_name == "Home"
        assert ctx.space_kind == "lobby"
        lobby = session.get(Space, "home")
        assert lobby.is_active is True
        assert lobby.deleted_at is None
