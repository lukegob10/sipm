from types import SimpleNamespace

import pytest

from backend.app.models import Space, SpaceMembership, User
from backend.app.routes import users
from backend.app.schemas import UserUpdate
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("lookup", ["id", "soeid"])
def test_committed_user_edit_invalidates_cache_if_refresh_fails(db_sessionmaker, monkeypatch, lookup):
    space = SpaceContext(space_id="space", space_name="Space", space_role="space_admin", is_global_admin=True)
    actor = SimpleNamespace(user_id="admin", role="global_admin", is_active=True)
    with db_sessionmaker() as session:
        session.add(Space(space_id="space", name="Space", slug="space"))
        session.add(User(user_id="user", soeid="user", email="user@example.test", display_name="Original",
                         password_hash="unused", role="user", is_active=True))
        session.add(SpaceMembership(space_id="space", user_id="user", role="member"))
        session.commit()
        invalidations = []
        monkeypatch.setattr(users, "_invalidate_user_caches_for_user_memberships", lambda _session, user_id: invalidations.append(user_id))
        monkeypatch.setattr(session, "refresh", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("refresh failed")))
        with pytest.raises(RuntimeError, match="refresh failed"):
            update = users.update_user if lookup == "id" else users.update_user_by_soeid
            update("user", UserUpdate(display_name="Changed"), session=session, space_ctx=space, current_user=actor)
        assert invalidations == ["user"]
    with db_sessionmaker() as session:
        assert session.get(User, "user").display_name == "Changed"
