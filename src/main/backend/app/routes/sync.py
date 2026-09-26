import asyncio
import os
import sys
from contextlib import suppress

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..deps import authenticate_access_token, get_db, require_global_admin
from ..services.realtime import (
    WS_CLOSE_AUTH_INVALID,
    WS_CLOSE_SERVER_BUSY,
    WS_CLOSE_SPACE_INVALID,
    WebSocketRejected,
    connection_snapshot,
    heartbeat,
    register,
    unregister,
)
from ..services.spaces import resolve_active_space_context

router = APIRouter()


@router.get("/realtime/status")
def realtime_status(_admin=Depends(require_global_admin)):
    return connection_snapshot()


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


def _authenticate_websocket_context(
    session: Session,
    token: str | None,
    requested_space_id: str | None,
) -> tuple[str | None, str | None, int | None, str | None]:
    """Run synchronous database-backed websocket auth in a worker thread."""
    try:
        try:
            user = authenticate_access_token(session, token)
        except Exception:
            return None, None, WS_CLOSE_AUTH_INVALID, "auth-invalid"

        try:
            ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
        except Exception:
            return None, None, WS_CLOSE_SPACE_INVALID, "space-invalid"

        if requested_space_id and ctx.space_id != requested_space_id:
            return None, None, WS_CLOSE_SPACE_INVALID, "space-mismatch"
        return user.user_id, ctx.space_id, None, None
    finally:
        # Keep the session's complete lifecycle on the same worker thread that
        # performed its synchronous database queries.
        session.close()


async def _authenticate_websocket_context_in_thread(
    session: Session,
    token: str | None,
    requested_space_id: str | None,
) -> tuple[str | None, str | None, int | None, str | None]:
    worker_task = asyncio.create_task(
        run_in_threadpool(
            _authenticate_websocket_context,
            session,
            token,
            requested_space_id,
        )
    )
    cancellation_requested = False
    while True:
        try:
            result = await asyncio.shield(worker_task)
            break
        except asyncio.CancelledError:
            # Keep the Session alive until the worker has finished its final
            # query and close, even after repeated request cancellation.
            cancellation_requested = True
            if worker_task.done():
                with suppress(BaseException):
                    worker_task.result()
                break
    if cancellation_requested:
        raise asyncio.CancelledError
    return result


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
    requested_space_id = _ws_requested_space_id(ws)
    try:
        user_id, space_id, rejection_code, rejection_reason = await _authenticate_websocket_context_in_thread(
            session,
            token,
            requested_space_id,
        )
    except Exception:
        await _reject_websocket(ws, code=WS_CLOSE_SERVER_BUSY, reason="server-error")
        return
    if rejection_code is not None:
        await _reject_websocket(ws, code=rejection_code, reason=rejection_reason or "")
        return
    if not user_id or not space_id:
        await _reject_websocket(ws, code=WS_CLOSE_SERVER_BUSY, reason="server-error")
        return

    try:
        await register(ws, user_id=user_id, space_id=space_id)
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
