from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.auth.auth import create_token
from backend.app.models import AuthSession, Space, SpaceMembership, User
from backend.app.routes.sync import websocket_endpoint
from backend.app.services import realtime


class Socket:
    def __init__(self, token):
        self.cookies = {"access_token": token}
        self.query_params = {"space_id": "space-a"}
        self.headers = {}
        self.accepted = asyncio.Event()
        self.messages = []
        self.closed = []
        self.receive = asyncio.Event()

    async def accept(self):
        self.accepted.set()

    async def receive_text(self):
        await self.receive.wait()
        raise RuntimeError("closed")

    async def send_json(self, message):
        self.messages.append(message)

    async def close(self, code, reason):
        self.closed.append((code, reason))
        self.receive.set()


@pytest.fixture
async def connected(db_sessionmaker):
    with db_sessionmaker() as session:
        session.add_all([
            User(user_id="socket-user", soeid="socketuser", email="socket@example.com",
                 display_name="Socket User", password_hash="unused", role="user", is_active=True),
            Space(space_id="space-a", name="Space A", slug="space-a", is_active=True),
            Space(space_id="space-b", name="Space B", slug="space-b", is_active=True),
            AuthSession(session_id="socket-session", user_id="socket-user"),
            SpaceMembership(space_id="space-a", user_id="socket-user", role="member", status="active"),
            SpaceMembership(space_id="space-b", user_id="socket-user", role="member", status="active"),
        ])
        session.commit()
    token = create_token("socket-user", "user", "access", session_id="socket-session")
    socket = Socket(token)
    endpoint = asyncio.create_task(websocket_endpoint(socket, session=db_sessionmaker()))
    await asyncio.wait_for(socket.accepted.wait(), 2)
    try:
        yield socket
    finally:
        socket.receive.set()
        await asyncio.wait_for(endpoint, 2)


@pytest.mark.anyio
async def test_refresh_rechecks_access_without_redecoding_original_token(connected, monkeypatch):
    # A refreshed browser token does not replace the original websocket cookie.
    monkeypatch.setattr("backend.app.deps.decode_token", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    await realtime.broadcast_refresh("tasks", space_id="space-b")
    assert connected.messages == []
    await realtime.broadcast_refresh("tasks", space_id="space-a")
    assert connected.messages == [{"type": "refresh", "entity": "tasks"}]
    assert connected.closed == []


@pytest.mark.anyio
@pytest.mark.parametrize("change,code", [
    ("revoked", realtime.WS_CLOSE_AUTH_INVALID),
    ("idle", realtime.WS_CLOSE_AUTH_INVALID),
    ("inactive", realtime.WS_CLOSE_AUTH_INVALID),
    ("locked", realtime.WS_CLOSE_AUTH_INVALID),
    ("password", realtime.WS_CLOSE_AUTH_INVALID),
    ("membership", realtime.WS_CLOSE_SPACE_INVALID),
    ("space", realtime.WS_CLOSE_SPACE_INVALID),
])
async def test_revoked_connection_gets_no_refresh(connected, db_sessionmaker, change, code):
    with db_sessionmaker() as session:
        user = session.get(User, "socket-user")
        auth_session = session.get(AuthSession, "socket-session")
        space = session.get(Space, "space-a")
        membership = session.query(SpaceMembership).filter_by(space_id="space-a", user_id="socket-user").one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if change == "revoked":
            auth_session.revoked_at = now
        elif change == "idle":
            auth_session.last_activity_at = now - timedelta(days=1)
        elif change == "inactive":
            user.is_active = False
        elif change == "locked":
            user.locked_until = now + timedelta(minutes=1)
        elif change == "password":
            user.password_changed_at = now + timedelta(seconds=5)
        elif change == "membership":
            membership.status = "inactive"
        else:
            space.is_active = False
        session.commit()
    await realtime.broadcast_refresh("tasks", space_id="space-a")
    assert connected.messages == []
    assert connected.closed == [(code, "auth-invalid" if code == realtime.WS_CLOSE_AUTH_INVALID else "space-invalid")]
    assert connected not in realtime.connections


@pytest.mark.anyio
async def test_revalidation_database_error_fails_closed(connected, monkeypatch):
    def fail(_identity):
        raise RuntimeError("database unavailable")
    monkeypatch.setattr("backend.app.routes.sync._revalidate_websocket_identity", fail)
    await realtime.broadcast_refresh("tasks", space_id="space-a")
    assert connected.messages == []
    assert connected.closed == [(realtime.WS_CLOSE_SERVER_BUSY, "server-error")]


@pytest.mark.anyio
async def test_disconnect_during_revalidation_does_not_send(monkeypatch):
    socket = Socket("unused")
    checking = asyncio.Event()
    proceed = asyncio.Event()

    async def authorize():
        checking.set()
        await proceed.wait()
        return None

    await realtime.register(socket, user_id="pending-user", space_id="pending-space", authorize=authorize)
    broadcast = asyncio.create_task(realtime.broadcast_refresh("tasks", space_id="pending-space"))
    await asyncio.wait_for(checking.wait(), 2)
    realtime.unregister(socket)
    proceed.set()
    await asyncio.wait_for(broadcast, 2)
    assert socket.messages == []


@pytest.mark.anyio
async def test_concurrent_broadcasts_do_not_send_after_failed_revalidation():
    socket = Socket("unused")
    checking = asyncio.Event()
    proceed = asyncio.Event()
    checks = 0

    async def authorize():
        nonlocal checks
        checks += 1
        checking.set()
        await proceed.wait()
        return realtime.WS_CLOSE_AUTH_INVALID, "auth-invalid"

    await realtime.register(socket, user_id="pending-user", space_id="pending-space", authorize=authorize)
    first = asyncio.create_task(realtime.broadcast_refresh("tasks", space_id="pending-space"))
    await asyncio.wait_for(checking.wait(), 2)
    second = asyncio.create_task(realtime.broadcast_refresh("projects", space_id="pending-space"))
    await asyncio.sleep(0)
    proceed.set()
    await asyncio.wait_for(asyncio.gather(first, second), 2)
    assert checks == 1
    assert socket.messages == []
    assert socket.closed == [(realtime.WS_CLOSE_AUTH_INVALID, "auth-invalid")]


@pytest.mark.anyio
async def test_refresh_database_check_does_not_block_event_loop(connected, monkeypatch):
    import threading
    from backend.app.routes import sync

    original = sync._revalidate_websocket_identity
    started = threading.Event()
    release = threading.Event()

    def slow_check(identity):
        started.set()
        if not release.wait(2):
            raise TimeoutError("test failed to release database check")
        return original(identity)

    monkeypatch.setattr(sync, "_revalidate_websocket_identity", slow_check)
    broadcast = asyncio.create_task(realtime.broadcast_refresh("tasks", space_id="space-a"))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 1.5)
        assert not broadcast.done()
    finally:
        release.set()
    await asyncio.wait_for(broadcast, 3)
    assert connected.messages == [{"type": "refresh", "entity": "tasks"}]


@pytest.mark.anyio
async def test_revalidation_fanout_is_bounded_and_does_not_exhaust_request_workers(
    connected, db_sessionmaker, monkeypatch
):
    import threading
    from backend.app.routes import sync
    from starlette.concurrency import run_in_threadpool

    sockets = [connected]
    endpoints = []
    for _ in range(7):
        socket = Socket(connected.cookies["access_token"])
        endpoint = asyncio.create_task(websocket_endpoint(socket, session=db_sessionmaker()))
        endpoints.append(endpoint)
        sockets.append(socket)
        await asyncio.wait_for(socket.accepted.wait(), 2)

    original = sync._revalidate_websocket_identity
    release = threading.Event()
    enough_started = threading.Event()
    guard = threading.Lock()
    active = 0
    peak = 0

    def blocked_check(identity):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
            if active == sync._REVALIDATION_CONCURRENCY:
                enough_started.set()
        try:
            if not release.wait(5):
                raise TimeoutError("test failed to release database checks")
            return original(identity)
        finally:
            with guard:
                active -= 1

    monkeypatch.setattr(sync, "_revalidate_websocket_identity", blocked_check)
    broadcast = asyncio.create_task(realtime.broadcast_refresh("tasks", space_id="space-a"))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(enough_started.wait, 2), 2.5)
        # Normal synchronous request work has a separate worker capacity.
        assert await asyncio.wait_for(run_in_threadpool(lambda: "available"), 1) == "available"
        await asyncio.sleep(0.05)
        assert peak == sync._REVALIDATION_CONCURRENCY
    finally:
        release.set()
        await asyncio.wait_for(broadcast, 5)
        for socket in sockets[1:]:
            socket.receive.set()
        await asyncio.wait_for(asyncio.gather(*endpoints), 3)
    assert all(socket.messages == [{"type": "refresh", "entity": "tasks"}] for socket in sockets)


@pytest.mark.anyio
async def test_cancelled_revalidation_retains_capacity_until_worker_finishes(connected, monkeypatch):
    import threading
    from backend.app.routes import sync

    started = threading.Event()
    release = threading.Event()

    def blocked_check(_identity):
        started.set()
        if not release.wait(3):
            raise TimeoutError("test failed to release database check")
        return None

    monkeypatch.setattr(sync, "_revalidate_websocket_identity", blocked_check)
    broadcast = asyncio.create_task(realtime.broadcast_refresh("tasks", space_id="space-a"))
    try:
        assert await asyncio.wait_for(asyncio.to_thread(started.wait, 1), 1.5)
        limiter = sync._revalidation_limiter()
        broadcast.cancel()
        await asyncio.sleep(0.02)
        assert limiter.borrowed_tokens == 1
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await broadcast
    assert limiter.borrowed_tokens == 0
    assert connected.messages == []


def test_websocket_protocol_closes_after_session_revocation(db_sessionmaker):
    from functools import partial
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from backend.app.deps import get_db
    from backend.app.routes.sync import router

    with db_sessionmaker() as session:
        session.add_all([
            User(user_id="protocol-user", soeid="protocoluser", email="protocol@example.com",
                 display_name="Protocol User", password_hash="unused", role="user", is_active=True),
            Space(space_id="protocol-space", name="Protocol Space", slug="protocol-space"),
            AuthSession(session_id="protocol-session", user_id="protocol-user"),
            SpaceMembership(space_id="protocol-space", user_id="protocol-user", role="member", status="active"),
        ])
        session.commit()
    token = create_token("protocol-user", "user", "access", session_id="protocol-session")
    app = FastAPI()
    app.include_router(router)

    def test_db():
        with db_sessionmaker() as session:
            yield session

    app.dependency_overrides[get_db] = test_db
    with TestClient(app) as client:
        with client.websocket_connect(
            "/ws?space_id=protocol-space", headers={"cookie": f"access_token={token}"}
        ) as socket:
            client.portal.call(partial(realtime.broadcast_refresh, "tasks", space_id="protocol-space"))
            assert socket.receive_json() == {"type": "refresh", "entity": "tasks"}
            with db_sessionmaker() as session:
                session.get(AuthSession, "protocol-session").revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
                session.commit()
            client.portal.call(partial(realtime.broadcast_refresh, "tasks", space_id="protocol-space"))
            with pytest.raises(WebSocketDisconnect) as disconnected:
                socket.receive_json()
            assert disconnected.value.code == realtime.WS_CLOSE_AUTH_INVALID
