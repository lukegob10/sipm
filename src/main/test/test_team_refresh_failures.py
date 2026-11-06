from datetime import datetime, timezone
import re

import pytest
from sqlalchemy import event

from backend.app.models import Space, SpaceMembership, Team, User
from backend.app.routes import teams
from backend.app.schemas import TeamCreate, TeamUpdate
from backend.app.services.spaces import SpaceContext


@pytest.mark.parametrize("operation", ["create", "restore", "rename"])
def test_committed_team_change_invalidates_cache_if_refresh_fails(
    db_sessionmaker, monkeypatch, operation
):
    space = SpaceContext(
        space_id="team-refresh", space_name="Team refresh", space_role="member", is_global_admin=True
    )
    with db_sessionmaker() as session:
        session.add(Space(space_id=space.space_id, name=space.space_name, slug=space.space_id))
        if operation != "create":
            session.add(
                Team(
                    team_id="team",
                    space_id=space.space_id,
                    name="Original",
                    deleted_at=datetime.now(timezone.utc) if operation == "restore" else None,
                )
            )
        if operation == "rename":
            session.add(User(user_id="user", soeid="user", email="user@example.test", display_name="User",
                             password_hash="unused", role="user", is_active=True, team_tag="Original"))
            session.add(SpaceMembership(space_id=space.space_id, user_id="user", role="member"))
        session.commit()
        invalidations = []
        monkeypatch.setattr(teams, "invalidate_space", lambda space_id, scopes: invalidations.append((space_id, scopes)))
        monkeypatch.setattr(session, "refresh", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("refresh failed")))

        with pytest.raises(RuntimeError, match="refresh failed"):
            if operation == "rename":
                teams.update_team("team", TeamUpdate(name="Renamed"), session=session, space_ctx=space)
            else:
                name = "Original" if operation == "restore" else "Created"
                teams.create_team(TeamCreate(name=name), session=session, space_ctx=space)

        assert (space.space_id, ["teams"]) in invalidations
        if operation == "rename":
            assert (space.space_id, ["users"]) in invalidations

    with db_sessionmaker() as session:
        if operation == "create":
            assert session.query(Team).filter_by(name="Created").one()
        elif operation == "restore":
            assert session.get(Team, "team").deleted_at is None
        else:
            assert session.get(Team, "team").name == "Renamed"
            assert session.get(User, "user").team_tag == "Renamed"


def test_user_cache_invalidation_handles_large_team(db_sessionmaker, monkeypatch):
    engine = db_sessionmaker.kw["bind"]
    invalidations = []
    monkeypatch.setattr(teams, "invalidate_space", lambda space_id, scopes: invalidations.append((space_id, scopes)))

    def enforce_oracle_limit(_connection, _cursor, statement, _parameters, _context, _executemany):
        for match in re.finditer(r"\bIN\s*\(([^)]*)\)", statement, flags=re.IGNORECASE):
            assert match.group(1).count("?") <= 1000, "Oracle IN list exceeds 1000 expressions"

    with db_sessionmaker() as session:
        session.add(SpaceMembership(space_id="space", user_id="user-0", role="member"))
        session.commit()
        event.listen(engine, "before_cursor_execute", enforce_oracle_limit)
        try:
            teams._invalidate_user_caches_for_user_memberships(
                session, {f"user-{index}" for index in range(1001)}
            )
        finally:
            event.remove(engine, "before_cursor_execute", enforce_oracle_limit)

    assert invalidations == [("space", ["users"])]
