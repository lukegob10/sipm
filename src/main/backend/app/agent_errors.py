from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .paths import API_PREFIX
from .security import security_message


AGENT_API_PREFIX = f"{API_PREFIX}/agent"
ERROR_CODE_HEADER = "X-Error-Code"

_DEFAULT_ERROR_CODES = {
    400: "BAD_REQUEST",
    401: "AUTH_REQUIRED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "REQUEST_TOO_LARGE",
    422: "REQUEST_VALIDATION_ERROR",
    429: "RATE_LIMITED",
}

_DEFAULT_ERROR_MESSAGES = {
    400: "Agent request is invalid",
    401: "Authentication is required",
    403: "Agent request is not permitted",
    404: "Agent resource was not found",
    405: "HTTP method is not allowed",
    409: "Agent request conflicts with current state",
    413: "Agent request is too large",
    422: "Agent request validation failed",
    429: "Agent request rate limit exceeded",
}


def _is_agent_request(request: Request) -> bool:
    path = request.url.path.rstrip("/")
    return path == AGENT_API_PREFIX or path.startswith(f"{AGENT_API_PREFIX}/")


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or "")


def _error_code(status_code: int, headers: dict[str, str]) -> str:
    return headers.get(ERROR_CODE_HEADER) or _DEFAULT_ERROR_CODES.get(
        status_code, "AGENT_REQUEST_FAILED"
    )


def _error_body(
    request: Request,
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "message": message,
        "request_id": _request_id(request),
        "details": details if details is not None else {},
    }


async def agent_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if not _is_agent_request(request):
        return await http_exception_handler(request, exc)

    headers = dict(exc.headers or {})
    code = _error_code(exc.status_code, headers)
    headers[ERROR_CODE_HEADER] = code
    fallback = _DEFAULT_ERROR_MESSAGES.get(exc.status_code, "Agent request failed")
    detail = exc.detail
    message = security_message(detail, fallback)
    if isinstance(detail, dict) and "details" in detail:
        details = detail["details"]
    elif isinstance(detail, str) or detail is None:
        details = {}
    else:
        details = detail
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder(
            _error_body(
                request,
                code=code,
                message=message,
                details=details,
            )
        ),
        headers=headers,
    )


async def agent_request_validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    if not _is_agent_request(request):
        return await request_validation_exception_handler(request, exc)

    code = "REQUEST_VALIDATION_ERROR"
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(
            _error_body(
                request,
                code=code,
                message="Agent request validation failed",
                details={"errors": exc.errors()},
            )
        ),
        headers={ERROR_CODE_HEADER: code},
    )


def install_agent_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, agent_http_exception_handler)
    app.add_exception_handler(
        RequestValidationError,
        agent_request_validation_exception_handler,
    )
