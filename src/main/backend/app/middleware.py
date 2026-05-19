from __future__ import annotations

import json
import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, Request

from backend.app.paths import API_PREFIX
from backend.app.request_context import reset_request_id, set_request_id


logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "font-src 'self' data:; "
        "connect-src 'self' ws: wss:; "
        "frame-ancestors 'self'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def request_id_for(request: Request) -> str:
    candidate = str(request.headers.get(REQUEST_ID_HEADER, "")).strip()
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


def request_log_line(
    request: Request,
    *,
    request_id: str,
    status_code: int,
    duration_ms: int,
    error_category: str | None = None,
) -> str:
    client_ip = request.client.host if request.client else "-"
    space_context = getattr(request.state, "space_context", None)
    active_space_id = (
        str(getattr(space_context, "space_id", "") or "").strip()
        or str(request.headers.get("X-Space-Id", "")).strip()
        or str(request.cookies.get("active_space_id", "")).strip()
        or "-"
    )
    user = getattr(request.state, "user", None)
    try:
        user_id = getattr(user, "user_id", None)
    except Exception:
        user_id = None
    payload = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": status_code,
        "duration_ms": duration_ms,
        "client_ip": client_ip,
        "space_id": active_space_id,
        "user_id": user_id or "-",
        "auth_method": getattr(request.state, "auth_method", None) or "-",
    }
    if error_category:
        payload["error_category"] = error_category
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def register_observability_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def request_observability_middleware(request: Request, call_next):
        request_id = request_id_for(request)
        request.state.request_id = request_id
        request_token = set_request_id(request_id)
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = int((time.perf_counter() - started_at) * 1000)
            logger.exception(
                request_log_line(
                    request,
                    request_id=request_id,
                    status_code=500,
                    duration_ms=duration_ms,
                    error_category="unhandled_exception",
                )
            )
            raise
        finally:
            reset_request_id(request_token)

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        response.headers[REQUEST_ID_HEADER] = request_id
        for header_name, header_value in SECURITY_HEADERS.items():
            response.headers.setdefault(header_name, header_value)
        if request.url.path.startswith(f"{API_PREFIX}/"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        logger.info(
            request_log_line(
                request,
                request_id=request_id,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        )
        return response
