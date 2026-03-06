from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..deps import authenticate_access_token, get_db
from ..services.realtime import heartbeat, register, unregister
from ..services.spaces import resolve_active_space_context

router = APIRouter()


def _ws_requested_space_id(ws: WebSocket) -> str | None:
    query_params = getattr(ws, "query_params", {}) or {}
    query_space_id = query_params.get("space_id")
    if query_space_id:
        return query_space_id
    headers = getattr(ws, "headers", {}) or {}
    header_space_id = headers.get("X-Space-Id")
    if header_space_id:
        return header_space_id
    cookies = getattr(ws, "cookies", {}) or {}
    return cookies.get("active_space_id")


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, session: Session = Depends(get_db)):
    if not hasattr(session, "query"):
        await register(ws)
        await _run_websocket_session(ws)
        return

    cookies = getattr(ws, "cookies", {}) or {}
    query_params = getattr(ws, "query_params", {}) or {}
    token = cookies.get("access_token") or query_params.get("token")
    try:
        user = authenticate_access_token(session, token)
    except Exception:
        close = getattr(ws, "close", None)
        if close is not None:
            await close(code=1008)
        return

    requested_space_id = _ws_requested_space_id(ws)
    try:
        ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    except Exception:
        close = getattr(ws, "close", None)
        if close is not None:
            await close(code=1008)
        return

    if requested_space_id and ctx.space_id != requested_space_id:
        close = getattr(ws, "close", None)
        if close is not None:
            await close(code=1008)
        return

    try:
        await register(ws, user_id=user.user_id, space_id=ctx.space_id)
    except Exception:
        return

    await _run_websocket_session(ws)


async def _run_websocket_session(ws: WebSocket) -> None:
    try:
        while True:
            await ws.receive_text()
            heartbeat(ws)
    except WebSocketDisconnect:
        unregister(ws)
    except Exception:
        unregister(ws)
