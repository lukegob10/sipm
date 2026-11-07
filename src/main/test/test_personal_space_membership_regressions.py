from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from starlette.requests import Request

from backend.app.deps import current_space
from backend.app.models import Space, SpaceMembership, User
from backend.app.services.spaces import (
    _personal_space_visible_to,
    list_user_spaces,
    resolve_auth_space_context,
)


def _seed_spaces(session):
    owner = User(
        user_id="private-owner", soeid="privateowner", email="owner@example.com",
        display_name="Owner", password_hash="unused", role="user", is_active=True,
    )
    other = User(
        user_id="private-other", soeid="privateother", email="other@example.com",
        display_name="Other", password_hash="unused", role="user", is_active=True,
    )
    admin = User(
        user_id="private-admin", soeid="privateadmin", email="admin@example.com",
        display_name="Admin", password_hash="unused", role="global_admin", is_active=True,
    )
    private = Space(
        space_id="private-space", name="Private Space", slug="private-space",
        space_kind="personal", owner_user_id=owner.user_id, is_active=True,
    )
    work = Space(
        space_id="work-space", name="Work Space", slug="work-space",
        space_kind="collaboration", is_active=True,
    )
    session.add_all([owner, other, admin, private, work])
    session.add_all([
        SpaceMembership(space_id=private.space_id, user_id=owner.user_id, role="space_admin", status="active"),
        SpaceMembership(space_id=private.space_id, user_id=other.user_id, role="member", status="active"),
        SpaceMembership(space_id=work.space_id, user_id=other.user_id, role="member", status="active"),
    ])
    session.commit()


def _request_for_space(space_id):
    return Request({
        "type": "http", "method": "GET", "path": "/", "headers": [(b"x-space-id", space_id.encode())],
    })


def test_nonowner_personal_membership_does_not_grant_space_access(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed_spaces(session)
        other = session.get(User, "private-other")
        assert [space.space_id for space in list_user_spaces(session, other)] == ["work-space"]
        ctx, spaces = resolve_auth_space_context(session, other, "private-space")
        assert ctx.space_id == "work-space"
        assert [space.space_id for space in spaces] == ["work-space"]
        with pytest.raises(HTTPException) as denied:
            current_space(_request_for_space("private-space"), session, other)
        assert denied.value.status_code == 403


def test_owner_and_global_admin_personal_access_remains_unchanged(db_sessionmaker):
    with db_sessionmaker() as session:
        _seed_spaces(session)
        owner = session.get(User, "private-owner")
        assert [space.space_id for space in list_user_spaces(session, owner)] == ["private-space"]
        assert current_space(_request_for_space("private-space"), session, owner).space_id == "private-space"
        admin = session.get(User, "private-admin")
        assert current_space(_request_for_space("private-space"), session, admin).space_id == "private-space"


def test_legacy_missing_space_kind_is_treated_as_collaboration():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            f'CREATE TABLE "{Space.__tablename__}" '
            '(space_id TEXT, space_kind TEXT, owner_user_id TEXT)'
        )
        conn.exec_driver_sql(
            f'INSERT INTO "{Space.__tablename__}" VALUES (?, ?, ?)',
            [("legacy-null", None, None), ("legacy-blank", " ", None),
             ("private-other", "personal", "owner")],
        )
        visible = conn.scalars(
            select(Space.space_id).where(_personal_space_visible_to("other"))
        ).all()
    assert visible == ["legacy-null", "legacy-blank"]
