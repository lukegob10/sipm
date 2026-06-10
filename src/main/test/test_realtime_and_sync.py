from __future__ import annotations

import asyncio
import importlib
from datetime import timedelta

import pytest
from starlette.websockets import WebSocketDisconnect

import backend.app.routes.sync as sync_route
import backend.app.services.realtime as realtime
from backend.app.routes.sync import websocket_endpoint


@pytest.fixture(autouse=True)
def clear_realtime_connections():
    realtime.connections.clear()
    realtime._connection_meta.clear()
    realtime._user_connections.clear()
    try:
        yield
    finally:
        realtime.connections.clear()
        realtime._connection_meta.clear()
        realtime._user_connections.clear()


class StubWebSocket:
    def __init__(
        self,
        *,
        raise_on_send: bool = False,
        receive_exc: Exception | None = None,
        cookies: dict | None = None,
        query_params: dict | None = None,
        headers: dict | None = None,
    ):
        self.accepted = False
        self.raise_on_send = raise_on_send
        self.receive_exc = receive_exc
        self.sent: list[dict] = []
        self.close_calls: list[tuple[int | None, str | None]] = []
        self.cookies = cookies or {}
        self.query_params = query_params or {}
        self.headers = headers or {}

    async def accept(self):
        self.accepted = True

    async def close(self, code: int | None = None, reason: str | None = None):
        self.close_calls.append((code, reason))

    async def send_json(self, payload):
        if self.raise_on_send:
            raise RuntimeError("send failed")
        self.sent.append(payload)

    async def receive_text(self):
        if self.receive_exc is not None:
            raise self.receive_exc
        return "ping"


class SessionStub:
    def query(self, *_args, **_kwargs):
        return None


class DummyUser:
    user_id = "user-1"


class DummySpaceContext:
    def __init__(self, space_id: str):
        self.space_id = space_id


@pytest.mark.anyio
async def test_register_broadcast_unregister_prunes_dead_connections():
    ws_ok = StubWebSocket()
    ws_dead = StubWebSocket(raise_on_send=True)

    await realtime.register(ws_ok)
    await realtime.register(ws_dead)
    assert ws_ok.accepted is True
    assert ws_dead.accepted is True
    assert ws_ok in realtime.connections
    assert ws_dead in realtime.connections

    await realtime.broadcast_refresh("projects")
    assert ws_ok.sent == [{"type": "refresh", "entity": "projects"}]
    assert ws_dead not in realtime.connections

    realtime.unregister(ws_ok)
    assert ws_ok not in realtime.connections


@pytest.mark.anyio
async def test_realtime_status_endpoint_returns_connection_snapshot(client):
    ws = StubWebSocket()
    await realtime.register(ws, user_id="user-1", space_id="space-1")

    response = await client.get("/project-manager/api/realtime/status")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 1
    assert payload["by_space"] == {"space-1": 1}
    assert payload["by_user"] == {"user-1": 1}
    assert payload["limits"]["global"] == realtime.MAX_CONNECTIONS_GLOBAL


@pytest.mark.anyio
async def test_broadcast_prunes_idle_connections_with_reconnectable_close_code():
    ws_idle = StubWebSocket()
    ws_active = StubWebSocket()

    await realtime.register(ws_idle)
    await realtime.register(ws_active)
    realtime._connection_meta[ws_idle].last_seen = realtime._utc_now() - timedelta(
        seconds=realtime.IDLE_TIMEOUT_SECONDS + 1
    )

    await realtime.broadcast_refresh("teams")

    assert ws_idle.close_calls == [(realtime.WS_CLOSE_IDLE_TIMEOUT, "idle-timeout")]
    assert ws_idle not in realtime.connections
    assert ws_active.sent == [{"type": "refresh", "entity": "teams"}]


@pytest.mark.anyio
async def test_schedule_broadcast_creates_task_when_loop_running():
    ws = StubWebSocket()
    await realtime.register(ws)
    realtime.schedule_broadcast("solutions")
    await asyncio.sleep(0)  # allow the fire-and-forget task to run
    assert {"type": "refresh", "entity": "solutions"} in ws.sent


def test_schedule_broadcast_falls_back_to_asyncio_run(monkeypatch):
    ws = StubWebSocket()
    realtime.connections.add(ws)

    def no_loop():
        raise RuntimeError("no current loop")

    monkeypatch.setattr(asyncio, "get_event_loop", no_loop)
    realtime.schedule_broadcast("tasks")
    assert ws.sent == [{"type": "refresh", "entity": "tasks"}]


@pytest.mark.anyio
async def test_websocket_endpoint_unregisters_on_disconnect():
    ws = StubWebSocket(receive_exc=WebSocketDisconnect())
    await websocket_endpoint(ws)
    assert ws.accepted is True
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_unregisters_on_unexpected_exception():
    ws = StubWebSocket(receive_exc=RuntimeError("boom"))
    await websocket_endpoint(ws)
    assert ws.accepted is True
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_closes_with_auth_code_on_invalid_token(monkeypatch):
    ws = StubWebSocket(cookies={"access_token": "bad-token"})

    def reject_token(_session, _token):
        raise RuntimeError("invalid token")

    monkeypatch.setattr(sync_route, "authenticate_access_token", reject_token)

    await websocket_endpoint(ws, session=SessionStub())

    assert ws.accepted is True
    assert ws.close_calls == [(realtime.WS_CLOSE_AUTH_INVALID, "auth-invalid")]
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_rejects_query_token_auth(monkeypatch):
    ws = StubWebSocket(query_params={"token": "query-token"})

    def reject_token(_session, token):
        assert token is None
        raise RuntimeError("missing token")

    monkeypatch.setattr(sync_route, "authenticate_access_token", reject_token)

    await websocket_endpoint(ws, session=SessionStub())

    assert ws.accepted is True
    assert ws.close_calls == [(realtime.WS_CLOSE_AUTH_INVALID, "auth-invalid")]
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_rejects_anonymous_session_outside_tests(monkeypatch):
    ws = StubWebSocket()
    monkeypatch.setattr(sync_route, "_running_tests", lambda: False)

    await websocket_endpoint(ws)

    assert ws.accepted is True
    assert ws.close_calls == [(realtime.WS_CLOSE_AUTH_INVALID, "auth-invalid")]
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_closes_with_space_code_on_requested_space_mismatch(monkeypatch):
    ws = StubWebSocket(cookies={"access_token": "good-token"}, query_params={"space_id": "requested-space"})

    monkeypatch.setattr(sync_route, "authenticate_access_token", lambda _session, _token: DummyUser())
    monkeypatch.setattr(
        sync_route,
        "resolve_active_space_context",
        lambda _session, _user, requested_space_id=None: DummySpaceContext(
            "fallback-space" if requested_space_id else "fallback-space"
        ),
    )

    await websocket_endpoint(ws, session=SessionStub())

    assert ws.accepted is True
    assert ws.close_calls == [(realtime.WS_CLOSE_SPACE_INVALID, "space-mismatch")]
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_closes_with_per_user_limit_code(monkeypatch):
    ws = StubWebSocket(cookies={"access_token": "good-token"})

    monkeypatch.setattr(sync_route, "authenticate_access_token", lambda _session, _token: DummyUser())
    monkeypatch.setattr(sync_route, "resolve_active_space_context", lambda _session, _user, requested_space_id=None: DummySpaceContext("space-1"))

    async def reject_register(_ws, **_kwargs):
        raise realtime.WebSocketRejected(
            realtime.WS_CLOSE_CONNECTION_LIMIT,
            "Per-user websocket connection limit reached",
        )

    monkeypatch.setattr(sync_route, "register", reject_register)

    await websocket_endpoint(ws, session=SessionStub())

    assert ws.accepted is True
    assert ws.close_calls == [
        (realtime.WS_CLOSE_CONNECTION_LIMIT, "Per-user websocket connection limit reached")
    ]
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_closes_with_server_busy_code(monkeypatch):
    ws = StubWebSocket(cookies={"access_token": "good-token"})

    monkeypatch.setattr(sync_route, "authenticate_access_token", lambda _session, _token: DummyUser())
    monkeypatch.setattr(sync_route, "resolve_active_space_context", lambda _session, _user, requested_space_id=None: DummySpaceContext("space-1"))

    async def reject_register(_ws, **_kwargs):
        raise realtime.WebSocketRejected(
            realtime.WS_CLOSE_SERVER_BUSY,
            "Global websocket connection limit reached",
        )

    monkeypatch.setattr(sync_route, "register", reject_register)

    await websocket_endpoint(ws, session=SessionStub())

    assert ws.accepted is True
    assert ws.close_calls == [
        (realtime.WS_CLOSE_SERVER_BUSY, "Global websocket connection limit reached")
    ]
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_endpoint_closes_with_server_busy_code_on_unexpected_register_error(monkeypatch):
    ws = StubWebSocket(cookies={"access_token": "good-token"})

    monkeypatch.setattr(sync_route, "authenticate_access_token", lambda _session, _token: DummyUser())
    monkeypatch.setattr(
        sync_route,
        "resolve_active_space_context",
        lambda _session, _user, requested_space_id=None: DummySpaceContext("space-1"),
    )

    async def broken_register(_ws, **_kwargs):
        raise RuntimeError("register failed")

    monkeypatch.setattr(sync_route, "register", broken_register)

    await websocket_endpoint(ws, session=SessionStub())

    assert ws.accepted is True
    assert ws.close_calls == [(realtime.WS_CLOSE_SERVER_BUSY, "server-error")]
    assert ws not in realtime.connections


def test_realtime_module_rejects_invalid_global_connection_limit(monkeypatch):
    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_WS_MAX_CONNECTIONS_GLOBAL", "many")
            with pytest.raises(RuntimeError, match="SIPM_WS_MAX_CONNECTIONS_GLOBAL must be an integer."):
                importlib.reload(realtime)
    finally:
        importlib.reload(realtime)


def test_realtime_module_rejects_non_positive_per_user_limit(monkeypatch):
    try:
        with monkeypatch.context() as env:
            env.setenv("SIPM_WS_MAX_CONNECTIONS_PER_USER", "0")
            with pytest.raises(
                RuntimeError,
                match="SIPM_WS_MAX_CONNECTIONS_PER_USER must be greater than or equal to 1.",
            ):
                importlib.reload(realtime)
    finally:
        importlib.reload(realtime)
