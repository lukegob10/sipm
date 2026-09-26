from __future__ import annotations

import asyncio
import importlib
import threading
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
    realtime._pending_connections = 0
    realtime._pending_user_connections.clear()
    realtime._runtime_loop = None
    try:
        yield
    finally:
        realtime.connections.clear()
        realtime._connection_meta.clear()
        realtime._user_connections.clear()
        realtime._pending_connections = 0
        realtime._pending_user_connections.clear()
        realtime._runtime_loop = None


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


class BlockedAcceptWebSocket(StubWebSocket):
    def __init__(self):
        super().__init__()
        self.accept_started = asyncio.Event()
        self.accept_release = asyncio.Event()

    async def accept(self):
        self.accept_started.set()
        await self.accept_release.wait()
        await super().accept()


class SessionStub:
    def __init__(self):
        self.close_calls = 0
        self.events: list[str] = []

    def query(self, *_args, **_kwargs):
        return None

    def close(self):
        self.close_calls += 1
        self.events.append("session-close")


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
async def test_space_scoped_broadcast_only_reaches_connections_in_that_space():
    ws_space_one = StubWebSocket()
    ws_space_two = StubWebSocket()
    await realtime.register(ws_space_one, user_id="user-1", space_id="space-1")
    await realtime.register(ws_space_two, user_id="user-2", space_id="space-2")

    await realtime._broadcast_local_refresh("projects", space_id="space-1")

    assert ws_space_one.sent == [{"type": "refresh", "entity": "projects"}]
    assert ws_space_two.sent == []


@pytest.mark.anyio
async def test_register_reserves_global_connection_slot_before_accept(monkeypatch):
    monkeypatch.setattr(realtime, "MAX_CONNECTIONS_GLOBAL", 1)
    monkeypatch.setattr(realtime, "MAX_CONNECTIONS_PER_USER", 8)
    first = BlockedAcceptWebSocket()
    first_task = asyncio.create_task(realtime.register(first, user_id="user-1", space_id="space-1"))
    await asyncio.wait_for(first.accept_started.wait(), timeout=1)

    second = StubWebSocket()
    with pytest.raises(realtime.WebSocketRejected) as rejected:
        await realtime.register(second, user_id="user-2", space_id="space-2")

    assert rejected.value.code == realtime.WS_CLOSE_SERVER_BUSY
    assert second.accepted is False
    first.accept_release.set()
    await first_task
    assert len(realtime.connections) == 1


@pytest.mark.anyio
async def test_register_reserves_per_user_slot_before_accept(monkeypatch):
    monkeypatch.setattr(realtime, "MAX_CONNECTIONS_GLOBAL", 8)
    monkeypatch.setattr(realtime, "MAX_CONNECTIONS_PER_USER", 1)
    first = BlockedAcceptWebSocket()
    first_task = asyncio.create_task(realtime.register(first, user_id="user-1", space_id="space-1"))
    await asyncio.wait_for(first.accept_started.wait(), timeout=1)

    second = StubWebSocket()
    with pytest.raises(realtime.WebSocketRejected) as rejected:
        await realtime.register(second, user_id="user-1", space_id="space-2")

    assert rejected.value.code == realtime.WS_CLOSE_CONNECTION_LIMIT
    assert second.accepted is False
    first.accept_release.set()
    await first_task
    assert realtime.connection_snapshot()["by_user"] == {"user-1": 1}


@pytest.mark.anyio
async def test_fanout_sends_to_healthy_clients_and_reconnectably_closes_stalled_client(monkeypatch):
    monkeypatch.setattr(realtime, "_SEND_TIMEOUT_SECONDS", 0.05)
    healthy_delivered = asyncio.Event()

    class StalledWebSocket(StubWebSocket):
        async def send_json(self, _payload):
            await asyncio.Event().wait()

    class ObservedWebSocket(StubWebSocket):
        async def send_json(self, payload):
            await super().send_json(payload)
            healthy_delivered.set()

    stalled = StalledWebSocket()
    healthy = ObservedWebSocket()
    await realtime.register(stalled, user_id="user-1", space_id="space-1")
    await realtime.register(healthy, user_id="user-2", space_id="space-1")

    broadcast = asyncio.create_task(realtime._broadcast_local_refresh("tasks", space_id="space-1"))
    await asyncio.wait_for(healthy_delivered.wait(), timeout=0.5)
    await asyncio.wait_for(broadcast, timeout=0.5)

    assert healthy.sent == [{"type": "refresh", "entity": "tasks"}]
    assert stalled.close_calls == [(realtime.WS_CLOSE_IDLE_TIMEOUT, "refresh-send-failed")]
    assert stalled not in realtime.connections


@pytest.mark.anyio
async def test_schedule_broadcast_creates_task_when_loop_running():
    ws = StubWebSocket()
    await realtime.register(ws)
    realtime.schedule_broadcast("solutions")
    for _ in range(10):
        if ws.sent:
            break
        await asyncio.sleep(0)
    assert {"type": "refresh", "entity": "solutions"} in ws.sent


@pytest.mark.anyio
async def test_schedule_broadcast_from_worker_thread_uses_runtime_loop():
    ws = StubWebSocket()
    await realtime.register(ws, space_id="space-1")
    await realtime.start_runtime()

    thread = threading.Thread(
        target=lambda: realtime.schedule_broadcast(
            "agent_change_requests",
            space_id="space-1",
        )
    )
    thread.start()
    thread.join(timeout=2)

    assert not thread.is_alive()
    for _ in range(10):
        if ws.sent:
            break
        await asyncio.sleep(0.01)
    assert ws.sent == [{"type": "refresh", "entity": "agent_change_requests"}]


def test_schedule_broadcast_falls_back_to_asyncio_run(monkeypatch):
    ws = StubWebSocket()
    realtime.connections.add(ws)

    def no_loop():
        raise RuntimeError("no current loop")

    monkeypatch.setattr(asyncio, "get_event_loop", no_loop)
    realtime.schedule_broadcast("tasks")
    assert ws.sent == [{"type": "refresh", "entity": "tasks"}]


@pytest.mark.anyio
async def test_broadcast_refresh_offloads_sync_redis_publish_from_event_loop(monkeypatch):
    loop_thread = threading.get_ident()
    publish_threads = []

    def publish(_entity, *, space_id=None):
        publish_threads.append(threading.get_ident())
        assert space_id == "space-1"
        return True

    monkeypatch.setattr(realtime.coordination, "uses_redis", lambda: True)
    monkeypatch.setattr(realtime.coordination, "publish_refresh", publish)

    await realtime.broadcast_refresh("tasks", space_id="space-1")

    assert len(publish_threads) == 1
    assert publish_threads[0] != loop_thread


@pytest.mark.anyio
async def test_schedule_broadcast_returns_while_redis_publish_is_blocked(monkeypatch):
    publish_started = threading.Event()
    publish_release = threading.Event()
    caller_returned = threading.Event()
    loop = asyncio.get_running_loop()

    def publish(_entity, *, space_id=None):
        publish_started.set()
        publish_release.wait(2)
        return True

    monkeypatch.setattr(realtime.coordination, "uses_redis", lambda: True)
    monkeypatch.setattr(realtime.coordination, "publish_refresh", publish)
    realtime._runtime_loop = loop

    def caller():
        realtime.schedule_broadcast("tasks", space_id="space-1")
        caller_returned.set()

    thread = threading.Thread(target=caller)
    thread.start()
    returned_before_publish_finished = False
    try:
        returned_before_publish_finished = await asyncio.wait_for(
            asyncio.to_thread(caller_returned.wait, 0.25),
            timeout=0.5,
        )
        await asyncio.wait_for(asyncio.to_thread(publish_started.wait, 1), timeout=1.5)
    finally:
        publish_release.set()
        await asyncio.to_thread(thread.join, 1)

    assert returned_before_publish_finished is True


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
async def test_websocket_endpoint_closes_session_before_receive_loop(monkeypatch):
    session = SessionStub()
    ws = StubWebSocket(cookies={"access_token": "good-token"})
    receive_started = False

    monkeypatch.setattr(
        sync_route,
        "authenticate_access_token",
        lambda _session, _token: DummyUser(),
    )
    monkeypatch.setattr(
        sync_route,
        "resolve_active_space_context",
        lambda _session, _user, requested_space_id=None: DummySpaceContext("space-1"),
    )

    async def disconnect_after_session_cleanup():
        nonlocal receive_started
        receive_started = True
        session.events.append("receive-start")
        raise WebSocketDisconnect()

    monkeypatch.setattr(ws, "receive_text", disconnect_after_session_cleanup)

    await websocket_endpoint(ws, session=session)

    assert receive_started is True
    assert session.close_calls == 1
    assert session.events == ["session-close", "receive-start"]
    assert ws.accepted is True
    assert ws not in realtime.connections


@pytest.mark.anyio
async def test_websocket_auth_offload_keeps_event_loop_responsive(monkeypatch):
    loop_thread = threading.get_ident()
    auth_started = threading.Event()
    auth_release = threading.Event()
    auth_released = threading.Event()
    auth_thread_ids = []

    class ThreadAwareSession(SessionStub):
        def close(self):
            self.close_thread_id = threading.get_ident()
            super().close()

    session = ThreadAwareSession()
    ws = StubWebSocket(cookies={"access_token": "good-token"}, receive_exc=WebSocketDisconnect())

    def slow_authenticate(_session, _token):
        auth_thread_ids.append(threading.get_ident())
        auth_started.set()
        auth_release.wait(2)
        return DummyUser()

    monkeypatch.setattr(sync_route, "authenticate_access_token", slow_authenticate)
    monkeypatch.setattr(
        sync_route,
        "resolve_active_space_context",
        lambda _session, _user, requested_space_id=None: DummySpaceContext("space-1"),
    )

    release_timer = threading.Timer(0.4, lambda: (auth_released.set(), auth_release.set()))
    release_timer.start()
    endpoint_task = asyncio.create_task(websocket_endpoint(ws, session=session))
    tick = asyncio.Event()
    released_at_tick = []

    async def prove_loop_is_running():
        await asyncio.sleep(0.01)
        released_at_tick.append(auth_released.is_set())
        tick.set()

    asyncio.create_task(prove_loop_is_running())
    try:
        await asyncio.wait_for(tick.wait(), timeout=0.25)
    finally:
        auth_release.set()
        release_timer.cancel()
    await endpoint_task

    assert released_at_tick == [False]
    assert auth_started.is_set()
    assert auth_thread_ids[0] != loop_thread
    assert session.close_thread_id == auth_thread_ids[0]
    assert session.events == ["session-close"]


@pytest.mark.anyio
async def test_websocket_auth_cancellation_waits_for_worker_to_close_session(monkeypatch):
    auth_started = threading.Event()
    auth_release = threading.Event()

    class ThreadAwareSession(SessionStub):
        def close(self):
            self.close_thread_id = threading.get_ident()
            super().close()

    session = ThreadAwareSession()
    ws = StubWebSocket(cookies={"access_token": "good-token"})

    def blocked_authenticate(_session, _token):
        auth_started.set()
        auth_release.wait(2)
        return DummyUser()

    monkeypatch.setattr(sync_route, "authenticate_access_token", blocked_authenticate)
    monkeypatch.setattr(
        sync_route,
        "resolve_active_space_context",
        lambda _session, _user, requested_space_id=None: DummySpaceContext("space-1"),
    )

    endpoint_task = asyncio.create_task(websocket_endpoint(ws, session=session))
    await asyncio.wait_for(asyncio.to_thread(auth_started.wait, 1), timeout=1.5)
    endpoint_task.cancel()
    await asyncio.sleep(0)
    waited_for_worker = not endpoint_task.done()
    endpoint_task.cancel()
    await asyncio.sleep(0)
    waited_after_second_cancel = not endpoint_task.done()
    auth_release.set()
    with pytest.raises(asyncio.CancelledError):
        await endpoint_task

    assert waited_for_worker is True
    assert waited_after_second_cancel is True
    assert session.close_calls == 1
    assert session.events == ["session-close"]


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
