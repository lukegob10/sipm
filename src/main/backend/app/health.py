from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from backend.app.auth.auth import validate_auth_configuration
from backend.app.config import startup_db_disabled
from backend.app.db.db import check_db_connection
from backend.app.frontend import frontend_bundle_error
from backend.app.services import coordination


def readiness_payload() -> tuple[int, dict]:
    checks: dict[str, dict[str, str]] = {}
    ready = True

    try:
        validate_auth_configuration()
        checks["auth"] = {"status": "ok"}
    except Exception as exc:
        ready = False
        checks["auth"] = {"status": "error", "detail": str(exc)}

    try:
        checks["coordination"] = {"status": "ok", "backend": coordination.validate_configuration()}
    except Exception as exc:
        ready = False
        checks["coordination"] = {"status": "error", "detail": str(exc)}

    frontend_error = frontend_bundle_error()
    if frontend_error:
        ready = False
        checks["frontend"] = {"status": "error", "detail": frontend_error}
    else:
        checks["frontend"] = {"status": "ok"}

    if startup_db_disabled():
        checks["db"] = {"status": "skipped", "detail": "startup disabled"}
    else:
        try:
            check_db_connection()
            checks["db"] = {"status": "ok"}
        except Exception as exc:
            ready = False
            checks["db"] = {"status": "error", "detail": str(exc)}

    return (200 if ready else 503), {"status": "ok" if ready else "not_ready", "checks": checks}


def register_health_routes(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness():
        status_code, payload = readiness_payload()
        return JSONResponse(payload, status_code=status_code)
