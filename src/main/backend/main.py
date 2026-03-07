from contextlib import asynccontextmanager
import os
import sys
import asyncio
from contextlib import suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    override_existing = str(os.getenv("SIPM_ENV_OVERRIDE", "true")).strip().lower() in {"1", "true", "yes", "on"}
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
        # Prefer env file values by default (configurable via SIPM_ENV_OVERRIDE=false).
        if key and (override_existing or key not in os.environ or not str(os.environ.get(key) or "").strip()):
            os.environ[key] = value


BASE_DIR = Path(__file__).resolve().parents[1]
_load_env_file(BASE_DIR / ".env")
_load_env_file(BASE_DIR / ".env.local")

# Also attempt to load repo-root env files as a fallback, without overriding non-empty values.
# This helps when running the app from different working directories.
try:
    REPO_DIR = BASE_DIR.parents[1]
    _load_env_file(REPO_DIR / ".env")
    _load_env_file(REPO_DIR / ".env.local")
except Exception:
    pass


from backend.app.db.db import init_db
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
from backend.app.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Avoid touching the on-disk DB during unit tests. Tests create their own in-memory DB
    # and override `get_db`/auth dependencies.
    disable_startup = os.getenv("SIPM_DISABLE_STARTUP", "").lower() == "true"
    running_tests = "pytest" in sys.modules or bool(os.getenv("PYTEST_CURRENT_TEST"))

    # Starlette/FastAPI run sync endpoints and sync generator dependencies in a threadpool via AnyIO.
    # In some sandboxed/test environments, the AnyIO threadpool can deadlock. We patch it out for tests.
    disable_threadpool = running_tests or os.getenv("SIPM_DISABLE_THREADPOOL", "").lower() == "true"
    if disable_threadpool:
        import anyio.to_thread

        if not getattr(anyio.to_thread.run_sync, "_jira_lite_patched", False):
            original_run_sync = anyio.to_thread.run_sync

            async def run_sync_no_threadpool(func, *args, abandon_on_cancel=False, limiter=None):  # type: ignore[override]
                return func(*args)

            run_sync_no_threadpool._jira_lite_patched = True  # type: ignore[attr-defined]
            run_sync_no_threadpool._jira_lite_original = original_run_sync  # type: ignore[attr-defined]
            anyio.to_thread.run_sync = run_sync_no_threadpool  # type: ignore[assignment]

    keepalive_task = None
    if running_tests or os.getenv("SIPM_KEEPALIVE_TASK", "").lower() == "true":
        async def _keepalive() -> None:
            while True:
                await asyncio.sleep(3600)

        keepalive_task = asyncio.create_task(_keepalive())

    if not disable_startup and not running_tests:
        init_db()
    yield
    if keepalive_task:
        keepalive_task.cancel()
        with suppress(asyncio.CancelledError):
            await keepalive_task


app = FastAPI(
    title="Jira-lite API",
    version="0.1.0",
    lifespan=lifespan,
    openapi_url=OPENAPI_PATH,
    docs_url=DOCS_PATH,
    redoc_url=REDOC_PATH,
)

# API under the app context path so the full product is self-contained.
app.include_router(api_router, prefix=API_PREFIX)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Serve frontend from src/main/ui
FRONTEND_DIR = BASE_DIR / "ui"
if FRONTEND_DIR.exists():
    frontend_static = StaticFiles(directory=FRONTEND_DIR, html=False)

    def _should_serve_spa(path: str) -> bool:
        normalized = str(path or "").strip("/")
        if not normalized:
            return True
        return "." not in normalized.split("/")[-1]

    async def _serve_frontend(request: Request, frontend_path: str = ""):
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
    def reset_password_page():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get(f"{RESET_PASSWORD_PATH}/")
    def reset_password_page_slash():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get(app_root_path(), include_in_schema=False)
    async def frontend_root(request: Request):
        return await _serve_frontend(request, "")

    @app.get(f"{APP_CONTEXT_PATH}/{{frontend_path:path}}" if APP_CONTEXT_PATH else "/{frontend_path:path}", include_in_schema=False)
    async def frontend_catchall(frontend_path: str, request: Request):
        return await _serve_frontend(request, frontend_path)
