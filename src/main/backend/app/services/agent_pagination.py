from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from fastapi import status

from ..auth.auth import SECRET_KEY
from ..security import security_http_exception


CURSOR_VERSION = 1


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}".encode("ascii"))


def _filter_fingerprint(filters: dict[str, Any]) -> str:
    serialized = json.dumps(
        filters,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def encode_position_cursor(
    *,
    scope: str,
    filters: dict[str, Any],
    position: dict[str, Any],
) -> str:
    payload = {
        "v": CURSOR_VERSION,
        "scope": scope,
        "filters": _filter_fingerprint(filters),
        "position": position,
    }
    encoded_payload = _b64encode(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    )
    signature = _b64encode(
        hmac.new(
            SECRET_KEY.encode("utf-8"),
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    return f"{encoded_payload}.{signature}"


def decode_position_cursor(
    cursor: str,
    *,
    scope: str,
    filters: dict[str, Any],
) -> dict[str, Any]:
    try:
        encoded_payload, encoded_signature = cursor.split(".", 1)
        expected_signature = _b64encode(
            hmac.new(
                SECRET_KEY.encode("utf-8"),
                encoded_payload.encode("ascii"),
                hashlib.sha256,
            ).digest()
        )
        if not hmac.compare_digest(encoded_signature, expected_signature):
            raise ValueError("cursor signature mismatch")
        payload = json.loads(_b64decode(encoded_payload))
        if payload.get("v") != CURSOR_VERSION:
            raise ValueError("cursor version mismatch")
        if payload.get("scope") != scope:
            raise ValueError("cursor scope mismatch")
        if payload.get("filters") != _filter_fingerprint(filters):
            raise ValueError("cursor filters mismatch")
        position = payload.get("position")
        if not isinstance(position, dict) or not position:
            raise ValueError("cursor position is missing")
        return position
    except Exception as exc:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_CURSOR",
            message="Cursor is invalid for this request",
        ) from exc


def encode_cursor(
    *,
    scope: str,
    filters: dict[str, Any],
    ordered_at: datetime,
    ordered_id: str,
) -> str:
    return encode_position_cursor(
        scope=scope,
        filters=filters,
        position={
            "ordered_at": ordered_at.isoformat(),
            "ordered_id": ordered_id,
        },
    )


def decode_cursor(
    cursor: str,
    *,
    scope: str,
    filters: dict[str, Any],
) -> tuple[datetime, str]:
    try:
        position = decode_position_cursor(
            cursor,
            scope=scope,
            filters=filters,
        )
        ordered_at = datetime.fromisoformat(str(position["ordered_at"]))
        ordered_id = str(position["ordered_id"]).strip()
        if not ordered_id:
            raise ValueError("cursor id is missing")
        return ordered_at, ordered_id
    except Exception as exc:
        raise security_http_exception(
            status_code=status.HTTP_400_BAD_REQUEST,
            code="INVALID_CURSOR",
            message="Cursor is invalid for this request",
        ) from exc
