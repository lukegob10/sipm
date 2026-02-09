import asyncio
from typing import Set

from fastapi import WebSocket

connections: Set[WebSocket] = set()


async def register(ws: WebSocket) -> None:
    await ws.accept()
    connections.add(ws)


def unregister(ws: WebSocket) -> None:
    connections.discard(ws)


async def broadcast_refresh(entity: str = "all") -> None:
    dead = []
    for ws in list(connections):
        try:
            await ws.send_json({"type": "refresh", "entity": entity})
        except Exception:
            dead.append(ws)
    for ws in dead:
        unregister(ws)


def schedule_broadcast(entity: str = "all") -> None:
    """Fire-and-forget broadcast; safe to call from sync contexts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(broadcast_refresh(entity))
        else:
            asyncio.run(broadcast_refresh(entity))
    except RuntimeError:
        asyncio.run(broadcast_refresh(entity))
