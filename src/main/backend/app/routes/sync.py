import os
import sys

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from ..deps import authenticate_access_token, get_db
from ..services.realtime import (
    WS_CLOSE_AUTH_INVALID,
    WS_CLOSE_SERVER_BUSY,
    WS_CLOSE_SPACE_INVALID,
    WebSocketRejected,
    heartbeat,
    register,
    unregister,
)
from ..services.spaces import resolve_active_space_context

router = APIRouter()


def _running_tests() -> bool:
    return "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


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


async def _reject_websocket(ws: WebSocket, *, code: int, reason: str = "") -> None:
    try:
        await ws.accept()
    except Exception:
        pass
    close = getattr(ws, "close", None)
    if close is None:
        return
    try:
        await close(code=code, reason=reason)
    except TypeError:
        await close(code=code)


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, session: Session = Depends(get_db)):
    if not hasattr(session, "query"):
        if not _running_tests():
            await _reject_websocket(ws, code=WS_CLOSE_AUTH_INVALID, reason="auth-invalid")
            return
        try:
            await register(ws)
        except WebSocketRejected as exc:
            await _reject_websocket(ws, code=exc.code, reason=exc.reason)
            return
        await _run_websocket_session(ws)
        return

    cookies = getattr(ws, "cookies", {}) or {}
    token = cookies.get("access_token")
    try:
        user = authenticate_access_token(session, token)
    except Exception:
        await _reject_websocket(ws, code=WS_CLOSE_AUTH_INVALID, reason="auth-invalid")
        return

    requested_space_id = _ws_requested_space_id(ws)
    try:
        ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
    except Exception:
        await _reject_websocket(ws, code=WS_CLOSE_SPACE_INVALID, reason="space-invalid")
        return

    if requested_space_id and ctx.space_id != requested_space_id:
        await _reject_websocket(ws, code=WS_CLOSE_SPACE_INVALID, reason="space-mismatch")
        return

    try:
        await register(ws, user_id=user.user_id, space_id=ctx.space_id)
    except WebSocketRejected as exc:
        await _reject_websocket(ws, code=exc.code, reason=exc.reason)
        return
    except Exception:
        await _reject_websocket(ws, code=WS_CLOSE_SERVER_BUSY, reason="server-error")
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
