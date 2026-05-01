from __future__ import annotations

from fastapi import HTTPException


def security_http_exception(*, status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail=message,
        headers={"X-Error-Code": code},
    )


def security_message(detail: object, fallback: str) -> str:
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message.strip():
            return message
    if isinstance(detail, str) and detail.strip():
        return detail
    return fallback
