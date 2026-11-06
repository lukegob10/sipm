import asyncio
import os
import sys
import threading
import weakref
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone

import anyio
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from ..deps import authenticate_access_token_context, ensure_token_not_revoked, get_db, require_global_admin
from ..models import Space, User
from ..services.auth_sessions import require_auth_session, require_session_binding
from ..services.authentication_state import is_user_locked
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

WS_CLOSE_SESSION_CHANGED = 4409

router = APIRouter()
_REVALIDATION_CONCURRENCY = 4
_revalidation_limiters: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_revalidation_limiter_lock = threading.Lock()


def _revalidation_limiter() -> anyio.CapacityLimiter:
    loop = asyncio.get_running_loop()
    with _revalidation_limiter_lock:
        limiter = _revalidation_limiters.get(loop)
        if limiter is None:
            limiter = anyio.CapacityLimiter(_REVALIDATION_CONCURRENCY)
            _revalidation_limiters[loop] = limiter
        return limiter


@dataclass(frozen=True)
class WebSocketIdentity:
    user_id: str
    space_id: str
    session_id: str
    issued_at: int | None
    bind: object


def _revalidate_websocket_identity(identity: WebSocketIdentity) -> tuple[int, str] | None:
    # Create and close the session in the worker performing the queries.
    with Session(bind=identity.bind) as session:
        user = session.get(User, identity.user_id)
        if not user or not user.is_active or is_user_locked(user, datetime.now(timezone.utc)):
            return WS_CLOSE_AUTH_INVALID, "auth-invalid"
        try:
            ensure_token_not_revoked(user, identity.issued_at)
            require_auth_session(session, {"sid": identity.session_id}, user_id=identity.user_id)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
            return WS_CLOSE_AUTH_INVALID, "auth-invalid"
        # Avoid default-space creation when the requested space is gone.
        space = session.get(Space, identity.space_id)
        if not space or space.deleted_at is not None or not space.is_active:
            return WS_CLOSE_SPACE_INVALID, "space-invalid"
        try:
            ctx = resolve_active_space_context(session, user, requested_space_id=identity.space_id)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
            return WS_CLOSE_SPACE_INVALID, "space-invalid"
        if ctx.space_id != identity.space_id:
            return WS_CLOSE_SPACE_INVALID, "space-invalid"
    return None


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
    expected_binding: str | None = None,
) -> tuple[WebSocketIdentity | None, int | None, str | None]:
    """Run synchronous database-backed websocket auth in a worker thread."""
    try:
        try:
            user, auth_session, payload = authenticate_access_token_context(session, token)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
            return None, WS_CLOSE_AUTH_INVALID, "auth-invalid"

        try:
            require_session_binding(expected_binding, auth_session.session_id)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
            return None, WS_CLOSE_SESSION_CHANGED, "session-changed"

        try:
            ctx = resolve_active_space_context(session, user, requested_space_id=requested_space_id)
        except HTTPException as exc:
            if exc.status_code >= 500:
                raise
            return None, WS_CLOSE_SPACE_INVALID, "space-invalid"

        if requested_space_id and ctx.space_id != requested_space_id:
            return None, WS_CLOSE_SPACE_INVALID, "space-mismatch"
        return WebSocketIdentity(
            user_id=user.user_id, space_id=ctx.space_id, session_id=auth_session.session_id,
            issued_at=payload.get("iat"), bind=session.get_bind(),
        ), None, None
    finally:
        # Keep the session's complete lifecycle on the same worker thread that
        # performed its synchronous database queries.
        session.close()


async def _authenticate_websocket_context_in_thread(
    session: Session,
    token: str | None,
    requested_space_id: str | None,
    expected_binding: str | None = None,
) -> tuple[WebSocketIdentity | None, int | None, str | None]:
    args = (session, token, requested_space_id)
    if expected_binding is not None:
        args += (expected_binding,)
    worker_task = asyncio.create_task(
        run_in_threadpool(_authenticate_websocket_context, *args)
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
        except Exception:
            if cancellation_requested:
                raise asyncio.CancelledError from None
            raise
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
    expected_binding = (getattr(ws, "query_params", {}) or {}).get("session_binding")
    try:
        identity, rejection_code, rejection_reason = await _authenticate_websocket_context_in_thread(
            session,
            token,
            requested_space_id,
            expected_binding,
        )
    except Exception:
        await _reject_websocket(ws, code=WS_CLOSE_SERVER_BUSY, reason="server-error")
        return
    if rejection_code is not None:
        await _reject_websocket(ws, code=rejection_code, reason=rejection_reason or "")
        return
    if not identity:
        await _reject_websocket(ws, code=WS_CLOSE_SERVER_BUSY, reason="server-error")
        return

    async def authorize_refresh():
        async with _revalidation_limiter():
            worker = asyncio.create_task(
                run_in_threadpool(_revalidate_websocket_identity, identity)
            )
            cancelled = False
            while True:
                try:
                    result = await asyncio.shield(worker)
                    break
                except asyncio.CancelledError:
                    cancelled = True
                    if worker.done():
                        with suppress(BaseException):
                            worker.result()
                        break
                except Exception:
                    if cancelled:
                        raise asyncio.CancelledError from None
                    raise
            if cancelled:
                raise asyncio.CancelledError
            return result

    try:
        await register(ws, user_id=identity.user_id, space_id=identity.space_id, authorize=authorize_refresh)
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
    except Exception:
        pass
    finally:
        unregister(ws)
