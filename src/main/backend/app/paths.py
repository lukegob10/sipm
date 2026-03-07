from __future__ import annotations

import os

DEFAULT_CONTEXT_PATH = "/project-manager"


def normalize_context_path(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "/":
        return ""
    return f"/{raw.strip('/')}"


APP_CONTEXT_PATH = normalize_context_path(os.getenv("SIPM_CONTEXT_PATH", DEFAULT_CONTEXT_PATH))
COOKIE_PATH = APP_CONTEXT_PATH or "/"


def app_path(path: str = "/") -> str:
    normalized = str(path or "/").strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return f"{APP_CONTEXT_PATH}{normalized}" if APP_CONTEXT_PATH else normalized


def app_root_path() -> str:
    return f"{APP_CONTEXT_PATH}/" if APP_CONTEXT_PATH else "/"


API_PREFIX = app_path("/api")
RESET_PASSWORD_PATH = app_path("/reset-password")
OPENAPI_PATH = app_path("/openapi.json")
DOCS_PATH = app_path("/docs")
REDOC_PATH = app_path("/redoc")
