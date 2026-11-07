import asyncio

import pytest

from backend.app.auth.auth import create_token
from backend.app.models import AuthSession, Space, SpaceMembership, User
from backend.app.routes.sync import WS_CLOSE_SESSION_CHANGED, websocket_endpoint
from backend.app.services import realtime
from backend.app.services.auth_sessions import session_binding


class Socket:
    def __init__(self, token, expected):
        self.cookies = {"access_token": token}
        self.query_params = {"space_id": "bound-space"}
        if expected is not None:
            self.query_params["session_binding"] = expected
        self.headers = {}
        self.accepted = asyncio.Event()
        self.finished = asyncio.Event()
        self.closed = []

    async def accept(self):
        self.accepted.set()

    async def receive_text(self):
        await self.finished.wait()
        raise RuntimeError("closed")

    async def close(self, code, reason):
        self.closed.append((code, reason))
        self.finished.set()


@pytest.mark.anyio
@pytest.mark.parametrize("expected,matching", [
    (None, True),
    (session_binding("bound-session"), True),
    (session_binding("different-session"), False),
    ("", False),
])
async def test_websocket_session_binding_checks_cookie_session(db_sessionmaker, expected, matching):
    with db_sessionmaker() as session:
        session.add_all([
            User(user_id="bound-user", soeid="bounduser", email="bound@example.com",
                 display_name="Bound User", password_hash="unused", role="user", is_active=True),
            Space(space_id="bound-space", name="Bound Space", slug="bound-space", is_active=True),
            AuthSession(session_id="bound-session", user_id="bound-user"),
            SpaceMembership(space_id="bound-space", user_id="bound-user", role="member", status="active"),
        ])
        session.commit()
    token = create_token("bound-user", "user", "access", session_id="bound-session")
    socket = Socket(token, expected)
    endpoint = asyncio.create_task(websocket_endpoint(socket, session=db_sessionmaker()))
    await asyncio.wait_for(socket.accepted.wait(), 2)
    try:
        if matching:
            assert socket in realtime.connections
            assert not socket.closed
        else:
            await asyncio.wait_for(endpoint, 2)
            assert socket.closed == [(WS_CLOSE_SESSION_CHANGED, "session-changed")]
            assert socket not in realtime.connections
    finally:
        socket.finished.set()
        await asyncio.wait_for(endpoint, 2)
