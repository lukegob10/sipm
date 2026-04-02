from contextlib import asynccontextmanager
import os
import sys
import asyncio
import logging
import re
import time
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException


def _bool_env(name: str, default: bool) -> bool:
    raw = str(os.getenv(name, "")).strip().lower()
    if not raw:
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean value.")


def _load_env_file(path: Path, *, override_existing: bool | None = None) -> None:
    if not path.exists():
        return
    if override_existing is None:
        override_existing = _bool_env("SIPM_ENV_OVERRIDE", False)
    for line in path.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        if "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        # Support common dotenv style: `export KEY=value`
        if key.lower().startswith("export "):
            parts = key.split(None, 1)
            key = parts[1].strip() if len(parts) > 1 else ""
        value = value.strip().strip("'").strip('"')
        # Support inline comments: KEY=value # comment
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        # Prefer explicit process env by default. Opt in to file overrides with
        # SIPM_ENV_OVERRIDE=true when local development needs it.
        if key and (override_existing or key not in os.environ or not str(os.environ.get(key) or "").strip()):
            os.environ[key] = value


def _repo_dir_for(base_dir: Path) -> Path:
    # Local source runs from <repo>/src/main, while the Docker image flattens that to /app.
    if len(base_dir.parents) > 1:
        return base_dir.parents[1]
    return base_dir


BASE_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = _repo_dir_for(BASE_DIR)
REPO_ENV = REPO_DIR / ".env"
REPO_ENV_LOCAL = REPO_DIR / ".env.local"

# Use the repo-root env files as the single source of truth.
# Keep `src/main/.env` only as a legacy fallback for older local setups.
if REPO_ENV.exists() or REPO_ENV_LOCAL.exists():
    _load_env_file(REPO_ENV)
    _load_env_file(REPO_ENV_LOCAL)
else:
    _load_env_file(BASE_DIR / ".env")
    _load_env_file(BASE_DIR / ".env.local")


from backend.app.auth.auth import validate_auth_configuration
from backend.app.auth.proxy_auth import maybe_inject_dev_proxy_headers, validate_proxy_auth_configuration
from backend.app.db.db import check_db_connection, init_db
from backend.app.paths import (
    API_PREFIX,
    APP_CONTEXT_PATH,
    DOCS_PATH,
    OPENAPI_PATH,
    REDOC_PATH,
    RESET_PASSWORD_PATH,
    app_path,
    app_root_path,
)
from backend.app.request_context import reset_request_id, set_request_id
from backend.app.routes import api_router
from backend.app.services import coordination
from backend.app.services.realtime import start_runtime as start_realtime_runtime
from backend.app.services.realtime import stop_runtime as stop_realtime_runtime


logger = logging.getLogger(__name__)
REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
FRONTEND_DIR = BASE_DIR / "ui"
FRONTEND_REQUIRED_FILES = (
    FRONTEND_DIR / "index.html",
    FRONTEND_DIR / "styles.css",
    FRONTEND_DIR / "js" / "app.js",
)


def _running_tests() -> bool:
    return "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))


def _startup_db_disabled() -> bool:
    return _bool_env("SIPM_DISABLE_STARTUP", False) or _running_tests()


def _request_id_for(request: Request) -> str:
    candidate = str(request.headers.get(REQUEST_ID_HEADER, "")).strip()
    if _REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return str(uuid4())


def _request_log_line(request: Request, *, request_id: str, status_code: int, duration_ms: int) -> str:
    client_ip = request.client.host if request.client else "-"
    active_space_id = str(request.headers.get("X-Space-Id", "")).strip() or "-"
    return (
        f"request_id={request_id} method={request.method} path={request.url.path} "
        f"status={status_code} duration_ms={duration_ms} client_ip={client_ip} "
        f"space_id={active_space_id}"
    )


def _frontend_bundle_error() -> str | None:
    missing = [path.relative_to(BASE_DIR).as_posix() for path in FRONTEND_REQUIRED_FILES if not path.exists()]
    if not missing:
        return None
    return f"Frontend bundle missing required files: {', '.join(missing)}"


def _readiness_payload() -> tuple[int, dict]:
    checks: dict[str, dict[str, str]] = {}
    ready = True

    try:
        validate_auth_configuration()
        checks["auth"] = {"status": "ok"}
    except Exception as exc:
        ready = False
        checks["auth"] = {"status": "error", "detail": str(exc)}

    try:
        validate_proxy_auth_configuration()
        checks["proxy_auth"] = {"status": "ok"}
    except Exception as exc:
        ready = False
        checks["proxy_auth"] = {"status": "error", "detail": str(exc)}

    frontend_error = _frontend_bundle_error()
    if frontend_error:
        ready = False
        checks["frontend"] = {"status": "error", "detail": frontend_error}
    else:
        checks["frontend"] = {"status": "ok"}

    if _startup_db_disabled():
        checks["db"] = {"status": "skipped", "detail": "startup disabled or test mode active"}
    else:
        try:
            check_db_connection()
            checks["db"] = {"status": "ok"}
        except Exception as exc:
            ready = False
            checks["db"] = {"status": "error", "detail": str(exc)}

    return (200 if ready else 503), {"status": "ok" if ready else "not_ready", "checks": checks}


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_auth_configuration()
    validate_proxy_auth_configuration()
    coordination.validate_configuration()
    # Avoid touching the on-disk DB during unit tests. Tests create their own in-memory DB
    # and override `get_db`/auth dependencies.
    disable_startup = _startup_db_disabled()
    running_tests = _running_tests()
    patched_run_sync = None
    original_run_sync = None

    # Starlette/FastAPI run sync endpoints and sync generator dependencies in a threadpool via AnyIO.
    # In some sandboxed/test environments, the AnyIO threadpool can deadlock. We patch it out for tests.
    disable_threadpool = running_tests or _bool_env("SIPM_DISABLE_THREADPOOL", False)
    if disable_threadpool:
        import anyio.to_thread

        if not getattr(anyio.to_thread.run_sync, "_jira_lite_patched", False):
            original_run_sync = anyio.to_thread.run_sync

            async def run_sync_no_threadpool(func, *args, abandon_on_cancel=False, limiter=None):  # type: ignore[override]
                return func(*args)

            run_sync_no_threadpool._jira_lite_patched = True  # type: ignore[attr-defined]
            run_sync_no_threadpool._jira_lite_original = original_run_sync  # type: ignore[attr-defined]
            anyio.to_thread.run_sync = run_sync_no_threadpool  # type: ignore[assignment]
            patched_run_sync = run_sync_no_threadpool

    keepalive_task = None
    try:
        await start_realtime_runtime()
        if running_tests or _bool_env("SIPM_KEEPALIVE_TASK", False):
            async def _keepalive() -> None:
                while True:
                    await asyncio.sleep(3600)

            keepalive_task = asyncio.create_task(_keepalive())

        if not disable_startup and not running_tests:
            init_db()
        yield
    finally:
        await stop_realtime_runtime()
        if keepalive_task:
            keepalive_task.cancel()
            with suppress(asyncio.CancelledError):
                await keepalive_task
        if patched_run_sync is not None and original_run_sync is not None:
            import anyio.to_thread

            if anyio.to_thread.run_sync is patched_run_sync:
                anyio.to_thread.run_sync = original_run_sync  # type: ignore[assignment]


app = FastAPI(
    title="SIPM API",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=OPENAPI_PATH,
    docs_url=DOCS_PATH,
    redoc_url=REDOC_PATH,
)

# API under the app context path so the full product is self-contained.
app.include_router(api_router, prefix=API_PREFIX)


@app.middleware("http")
async def request_observability_middleware(request: Request, call_next):
    maybe_inject_dev_proxy_headers(request.scope)
    request_id = _request_id_for(request)
    request.state.request_id = request_id
    request_token = set_request_id(request_id)
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        logger.exception(
            _request_log_line(
                request,
                request_id=request_id,
                status_code=500,
                duration_ms=duration_ms,
            )
        )
        raise
    finally:
        reset_request_id(request_token)

    duration_ms = int((time.perf_counter() - started_at) * 1000)
    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        _request_log_line(
            request,
            request_id=request_id,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
    )
    return response


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    status_code, payload = _readiness_payload()
    return JSONResponse(payload, status_code=status_code)


frontend_static = StaticFiles(directory=FRONTEND_DIR, html=False) if FRONTEND_DIR.exists() else None

def _should_serve_spa(path: str) -> bool:
    normalized = str(path or "").strip("/")
    if not normalized:
        return True
    return "." not in normalized.split("/")[-1]

async def _serve_frontend(request: Request, frontend_path: str = ""):
    frontend_error = _frontend_bundle_error()
    if frontend_error:
        return JSONResponse({"detail": frontend_error}, status_code=503)
    if frontend_static is None:
        return JSONResponse({"detail": "Frontend bundle is not configured."}, status_code=503)

    normalized = str(frontend_path or "").lstrip("/")
    response = None
    try:
        response = await frontend_static.get_response(normalized or ".", request.scope)
    except StarletteHTTPException as exc:
        if exc.status_code != 404:
            raise
    if response is not None and response.status_code != 404:
        return response
    if normalized.endswith("/") and _should_serve_spa(normalized.rstrip("/")):
        return RedirectResponse(app_path(f"/{normalized.rstrip('/')}"), status_code=307)
    if _should_serve_spa(normalized):
        return FileResponse(FRONTEND_DIR / "index.html")
    if response is not None:
        return response
    raise StarletteHTTPException(status_code=404)

if APP_CONTEXT_PATH:
    @app.get("/", include_in_schema=False)
    def app_root_redirect():
        return RedirectResponse(app_root_path(), status_code=307)

    @app.get(APP_CONTEXT_PATH, include_in_schema=False)
    def app_context_redirect():
        return RedirectResponse(app_root_path(), status_code=307)

@app.get(RESET_PASSWORD_PATH)
async def reset_password_page(request: Request):
    return await _serve_frontend(request, "reset-password")

@app.get(f"{RESET_PASSWORD_PATH}/")
async def reset_password_page_slash(request: Request):
    return await _serve_frontend(request, "reset-password/")

@app.get(app_root_path(), include_in_schema=False)
async def frontend_root(request: Request):
    return await _serve_frontend(request, "")

@app.get(f"{APP_CONTEXT_PATH}/{{frontend_path:path}}" if APP_CONTEXT_PATH else "/{frontend_path:path}", include_in_schema=False)
async def frontend_catchall(frontend_path: str, request: Request):
    return await _serve_frontend(request, frontend_path)
