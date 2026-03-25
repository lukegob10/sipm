from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Set

from fastapi import WebSocket


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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _touch(ws: WebSocket) -> None:
    meta = _connection_meta.get(ws)
    if meta:
        meta.last_seen = _utc_now()


def _stale_idle_connections() -> list[WebSocket]:
    if IDLE_TIMEOUT_SECONDS <= 0:
        return []
    cutoff = _utc_now() - timedelta(seconds=IDLE_TIMEOUT_SECONDS)
    return [ws for ws, meta in _connection_meta.items() if meta.last_seen < cutoff]


async def _prune_idle_connections() -> None:
    for ws in _stale_idle_connections():
        close = getattr(ws, "close", None)
        try:
            if close is not None:
                try:
                    await close(code=WS_CLOSE_IDLE_TIMEOUT, reason="idle-timeout")
                except TypeError:
                    await close(code=WS_CLOSE_IDLE_TIMEOUT)
        finally:
            unregister(ws)


def _user_connection_count(user_id: str) -> int:
    return len(_user_connections.get(user_id, set()))


async def register(
    ws: WebSocket,
    *,
    user_id: str | None = None,
    space_id: str | None = None,
) -> None:
    user_id = (user_id or DEFAULT_USER_ID).strip() or DEFAULT_USER_ID
    space_id = (space_id or DEFAULT_SPACE_ID).strip() or DEFAULT_SPACE_ID
    await _prune_idle_connections()
    if len(connections) >= MAX_CONNECTIONS_GLOBAL:
        raise WebSocketRejected(WS_CLOSE_SERVER_BUSY, "Global websocket connection limit reached")
    if _user_connection_count(user_id) >= MAX_CONNECTIONS_PER_USER:
        raise WebSocketRejected(WS_CLOSE_CONNECTION_LIMIT, "Per-user websocket connection limit reached")

    await ws.accept()
    connections.add(ws)
    _connection_meta[ws] = ConnectionMeta(user_id=user_id, space_id=space_id, last_seen=_utc_now())
    _user_connections.setdefault(user_id, set()).add(ws)


def unregister(ws: WebSocket) -> None:
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
    await _prune_idle_connections()
    dead = []
    for ws in list(connections):
        meta = _connection_meta.get(ws)
        if space_id and meta and meta.space_id != space_id:
            continue
        if space_id and not meta:
            continue
        try:
            await ws.send_json({"type": "refresh", "entity": entity})
            _touch(ws)
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister(ws)


def schedule_broadcast(entity: str = "all", *, space_id: str | None = None) -> None:
    """Fire-and-forget broadcast; safe to call from sync contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast_refresh(entity, space_id=space_id))
        else:
            asyncio.run(broadcast_refresh(entity, space_id=space_id))
    except RuntimeError:
        asyncio.run(broadcast_refresh(entity, space_id=space_id))


def connection_snapshot() -> Dict[str, object]:
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
