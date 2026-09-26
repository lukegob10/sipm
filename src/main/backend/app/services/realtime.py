from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Set

from fastapi import WebSocket

from . import coordination


def _int_env_with_default(name: str, default: int) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer.") from exc


MAX_CONNECTIONS_GLOBAL = _int_env_with_default("SIPM_WS_MAX_CONNECTIONS_GLOBAL", 400)
MAX_CONNECTIONS_PER_USER = _int_env_with_default("SIPM_WS_MAX_CONNECTIONS_PER_USER", 8)
IDLE_TIMEOUT_SECONDS = _int_env_with_default("SIPM_WS_IDLE_TIMEOUT_SECONDS", 600)
if MAX_CONNECTIONS_GLOBAL < 1:
    raise RuntimeError("SIPM_WS_MAX_CONNECTIONS_GLOBAL must be greater than or equal to 1.")
if MAX_CONNECTIONS_PER_USER < 1:
    raise RuntimeError("SIPM_WS_MAX_CONNECTIONS_PER_USER must be greater than or equal to 1.")
if IDLE_TIMEOUT_SECONDS < 0:
    raise RuntimeError("SIPM_WS_IDLE_TIMEOUT_SECONDS must be greater than or equal to 0.")
DEFAULT_USER_ID = "anonymous"
DEFAULT_SPACE_ID = "default"
WS_CLOSE_AUTH_INVALID = 4401
WS_CLOSE_SPACE_INVALID = 4403
WS_CLOSE_CONNECTION_LIMIT = 4408
WS_CLOSE_SERVER_BUSY = 1013
WS_CLOSE_IDLE_TIMEOUT = 1001
_SEND_TIMEOUT_SECONDS = 5.0


class WebSocketRejected(RuntimeError):
    def __init__(self, code: int, reason: str):
        super().__init__(reason)
        self.code = code
        self.reason = reason


@dataclass
class ConnectionMeta:
    user_id: str
    space_id: str
    last_seen: datetime


connections: Set[WebSocket] = set()
_connection_meta: Dict[WebSocket, ConnectionMeta] = {}
_user_connections: Dict[str, Set[WebSocket]] = {}
_pending_connections = 0
_pending_user_connections: Dict[str, int] = {}
_CONNECTION_LOCK = threading.RLock()
_runtime_loop: asyncio.AbstractEventLoop | None = None


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _touch(ws: WebSocket) -> None:
    with _CONNECTION_LOCK:
        meta = _connection_meta.get(ws)
        if meta:
            meta.last_seen = _utc_now()


def _stale_idle_connections() -> list[WebSocket]:
    if IDLE_TIMEOUT_SECONDS <= 0:
        return []
    cutoff = _utc_now() - timedelta(seconds=IDLE_TIMEOUT_SECONDS)
    with _CONNECTION_LOCK:
        return [ws for ws, meta in _connection_meta.items() if meta.last_seen < cutoff]


async def _close_connection(ws: WebSocket, *, code: int, reason: str) -> None:
    close = getattr(ws, "close", None)
    try:
        if close is not None:
            try:
                await asyncio.wait_for(
                    close(code=code, reason=reason),
                    timeout=_SEND_TIMEOUT_SECONDS,
                )
            except TypeError:
                await asyncio.wait_for(close(code=code), timeout=_SEND_TIMEOUT_SECONDS)
    except Exception:
        pass
    finally:
        unregister(ws)


async def _prune_idle_connections() -> None:
    for ws in _stale_idle_connections():
        await _close_connection(ws, code=WS_CLOSE_IDLE_TIMEOUT, reason="idle-timeout")


async def _broadcast_local_refresh(entity: str = "all", space_id: str | None = None) -> None:
    await _prune_idle_connections()
    with _CONNECTION_LOCK:
        recipients = [
            ws
            for ws in connections
            if not space_id
            or (
                (meta := _connection_meta.get(ws)) is not None
                and meta.space_id == space_id
            )
        ]

    async def send_one(ws: WebSocket) -> None:
        try:
            await asyncio.wait_for(
                ws.send_json({"type": "refresh", "entity": entity}),
                timeout=_SEND_TIMEOUT_SECONDS,
            )
            _touch(ws)
        except Exception:
            # A timed-out send leaves the browser believing it is still live.
            # Close with a reconnectable established-socket code before removal.
            await _close_connection(ws, code=WS_CLOSE_IDLE_TIMEOUT, reason="refresh-send-failed")

    await asyncio.gather(*(send_one(ws) for ws in recipients))


def _user_connection_count(user_id: str) -> int:
    with _CONNECTION_LOCK:
        return len(_user_connections.get(user_id, set()))


def _release_pending_connection(user_id: str) -> None:
    global _pending_connections
    with _CONNECTION_LOCK:
        _pending_connections -= 1
        pending_for_user = _pending_user_connections.get(user_id, 0) - 1
        if pending_for_user > 0:
            _pending_user_connections[user_id] = pending_for_user
        else:
            _pending_user_connections.pop(user_id, None)


async def register(
    ws: WebSocket,
    *,
    user_id: str | None = None,
    space_id: str | None = None,
) -> None:
    global _pending_connections
    user_id = (user_id or DEFAULT_USER_ID).strip() or DEFAULT_USER_ID
    space_id = (space_id or DEFAULT_SPACE_ID).strip() or DEFAULT_SPACE_ID
    await _prune_idle_connections()
    with _CONNECTION_LOCK:
        if len(connections) + _pending_connections >= MAX_CONNECTIONS_GLOBAL:
            raise WebSocketRejected(WS_CLOSE_SERVER_BUSY, "Global websocket connection limit reached")
        user_count = len(_user_connections.get(user_id, set())) + _pending_user_connections.get(user_id, 0)
        if user_count >= MAX_CONNECTIONS_PER_USER:
            raise WebSocketRejected(WS_CLOSE_CONNECTION_LIMIT, "Per-user websocket connection limit reached")
        _pending_connections += 1
        _pending_user_connections[user_id] = _pending_user_connections.get(user_id, 0) + 1

    try:
        await ws.accept()
    except BaseException:
        _release_pending_connection(user_id)
        raise

    with _CONNECTION_LOCK:
        _pending_connections -= 1
        pending_for_user = _pending_user_connections[user_id] - 1
        if pending_for_user > 0:
            _pending_user_connections[user_id] = pending_for_user
        else:
            _pending_user_connections.pop(user_id, None)
        connections.add(ws)
        _connection_meta[ws] = ConnectionMeta(user_id=user_id, space_id=space_id, last_seen=_utc_now())
        _user_connections.setdefault(user_id, set()).add(ws)


def unregister(ws: WebSocket) -> None:
    with _CONNECTION_LOCK:
        meta = _connection_meta.pop(ws, None)
        connections.discard(ws)
        if not meta:
            return
        user_set = _user_connections.get(meta.user_id)
        if not user_set:
            return
        user_set.discard(ws)
        if not user_set:
            _user_connections.pop(meta.user_id, None)


def heartbeat(ws: WebSocket) -> None:
    _touch(ws)


async def broadcast_refresh(entity: str = "all", *, space_id: str | None = None) -> None:
    await _publish_or_broadcast(entity, space_id=space_id)


async def _publish_or_broadcast(entity: str, *, space_id: str | None) -> None:
    if coordination.uses_redis():
        # redis-py is configured with a bounded socket timeout, but its sync
        # client must still stay off the ASGI event loop.
        if await asyncio.to_thread(coordination.publish_refresh, entity, space_id=space_id):
            return
    await _broadcast_local_refresh(entity, space_id=space_id)


def schedule_broadcast(entity: str = "all", *, space_id: str | None = None) -> None:
    """Fire-and-forget broadcast; safe to call from sync contexts."""
    broadcast = _publish_or_broadcast(entity, space_id=space_id)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        loop.create_task(broadcast)
        return
    if _runtime_loop is not None and _runtime_loop.is_running() and not _runtime_loop.is_closed():
        asyncio.run_coroutine_threadsafe(broadcast, _runtime_loop)
        return
    asyncio.run(broadcast)


async def start_runtime() -> None:
    global _runtime_loop
    _runtime_loop = asyncio.get_running_loop()
    if coordination.uses_redis():
        await coordination.start_refresh_listener(_broadcast_local_refresh)


async def stop_runtime() -> None:
    global _runtime_loop
    await coordination.stop_refresh_listener()
    _runtime_loop = None


def connection_snapshot() -> Dict[str, object]:
    with _CONNECTION_LOCK:
        by_space: Dict[str, int] = {}
        for meta in _connection_meta.values():
            by_space[meta.space_id] = by_space.get(meta.space_id, 0) + 1
        by_user = {user_id: len(ws_set) for user_id, ws_set in _user_connections.items()}
        return {
            "total": len(connections),
            "by_space": by_space,
            "by_user": by_user,
            "limits": {
                "global": MAX_CONNECTIONS_GLOBAL,
                "per_user": MAX_CONNECTIONS_PER_USER,
                "idle_timeout_seconds": IDLE_TIMEOUT_SECONDS,
            },
        }
