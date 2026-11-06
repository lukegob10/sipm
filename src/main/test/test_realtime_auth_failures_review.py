from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from backend.app.routes import sync
from backend.app.services import realtime


class _Session:
    def __init__(self):
        self.closed = False

    def query(self, *_args):
        raise AssertionError("Queries should be supplied by the mocked auth helpers")

    def close(self):
        self.closed = True


class _WebSocket:
    cookies = {"access_token": "valid-cookie"}
    query_params = {"space_id": "space-1"}
    headers = {}

    def __init__(self):
        self.close_calls = []

    async def accept(self):
        pass

    async def close(self, code, reason):
        self.close_calls.append((code, reason))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure_at, exception, expected_code",
    [
        ("auth", HTTPException(status_code=401), realtime.WS_CLOSE_AUTH_INVALID),
        ("space", HTTPException(status_code=403), realtime.WS_CLOSE_SPACE_INVALID),
        ("auth", HTTPException(status_code=503), realtime.WS_CLOSE_SERVER_BUSY),
        ("space", HTTPException(status_code=503), realtime.WS_CLOSE_SERVER_BUSY),
        ("auth", RuntimeError("database unavailable"), realtime.WS_CLOSE_SERVER_BUSY),
        ("space", RuntimeError("database unavailable"), realtime.WS_CLOSE_SERVER_BUSY),
    ],
)
async def test_websocket_distinguishes_rejection_from_server_failure(
    monkeypatch, failure_at, exception, expected_code
):
    session = _Session()
    socket = _WebSocket()

    def authenticate(_session, _token):
        if failure_at == "auth":
            raise exception
        return SimpleNamespace(user_id="user-1"), SimpleNamespace(session_id="session-1"), {}

    def resolve_space(_session, _user, requested_space_id):
        if failure_at == "space":
            raise exception
        return SimpleNamespace(space_id=requested_space_id)

    monkeypatch.setattr(sync, "authenticate_access_token_context", authenticate)
    monkeypatch.setattr(sync, "resolve_active_space_context", resolve_space)

    await sync.websocket_endpoint(socket, session=session)

    assert socket.close_calls[0][0] == expected_code
    assert session.closed
