from __future__ import annotations

import asyncio

import pytest
from starlette.websockets import WebSocketDisconnect

import backend.app.services.realtime as realtime
from backend.app.routes.sync import websocket_endpoint


@pytest.fixture(autouse=True)
def clear_realtime_connections():
    realtime.connections.clear()
    try:
        yield
    finally:
        realtime.connections.clear()


class StubWebSocket:
    def __init__(self, *, raise_on_send: bool = False, receive_exc: Exception | None = None):
        self.accepted = False
        self.raise_on_send = raise_on_send
        self.receive_exc = receive_exc
        self.sent: list[dict] = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, payload):
        if self.raise_on_send:
            raise RuntimeError("send failed")
        self.sent.append(payload)

    async def receive_text(self):
        if self.receive_exc is not None:
            raise self.receive_exc
        return "ping"


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
    realtime.schedule_broadcast("subcomponents")
    assert ws.sent == [{"type": "refresh", "entity": "subcomponents"}]


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
