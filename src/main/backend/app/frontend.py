from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from pathlib import Path

from backend.app.config import BASE_DIR, FRONTEND_DIR, FRONTEND_REQUIRED_FILES
from backend.app.paths import (
    APP_CONTEXT_PATH,
    RESET_PASSWORD_PATH,
    app_path,
    app_root_path,
)


def frontend_bundle_error(
    *,
    base_dir: Path = BASE_DIR,
    required_files: tuple[Path, ...] = FRONTEND_REQUIRED_FILES,
) -> str | None:
    missing = [
        path.relative_to(base_dir).as_posix()
        for path in required_files
        if not path.exists()
    ]
    if not missing:
        return None
    return f"Frontend bundle missing required files: {', '.join(missing)}"


def normalize_frontend_path(path: str) -> str:
    return str(path or "").lstrip("/")


def should_serve_spa(path: str) -> bool:
    normalized = str(path or "").strip("/")
    if not normalized:
        return True
    return "." not in normalized.split("/")[-1]


class FrontendServer:
    def __init__(
        self,
        *,
        base_dir: Path = BASE_DIR,
        frontend_dir: Path = FRONTEND_DIR,
        required_files: tuple[Path, ...] = FRONTEND_REQUIRED_FILES,
    ) -> None:
        self.base_dir = base_dir
        self.frontend_dir = frontend_dir
        self.required_files = required_files
        self.static = (
            StaticFiles(directory=frontend_dir, html=False)
            if frontend_dir.exists()
            else None
        )

    def bundle_error(self) -> str | None:
        if self.base_dir == BASE_DIR and self.required_files == FRONTEND_REQUIRED_FILES:
            return frontend_bundle_error()
        return frontend_bundle_error(
            base_dir=self.base_dir, required_files=self.required_files
        )

    async def serve(self, request: Request, frontend_path: str = ""):
        frontend_error = self.bundle_error()
        if frontend_error:
            return JSONResponse({"detail": frontend_error}, status_code=503)
        if self.static is None:
            return JSONResponse(
                {"detail": "Frontend bundle is not configured."}, status_code=503
            )

        normalized = normalize_frontend_path(frontend_path)
        response = None
        try:
            response = await self.static.get_response(normalized or ".", request.scope)
        except StarletteHTTPException as exc:
            if exc.status_code != 404:
                raise
        if response is not None and response.status_code != 404:
            return response
        if normalized.endswith("/") and should_serve_spa(normalized.rstrip("/")):
            return RedirectResponse(
                app_path(f"/{normalized.rstrip('/')}"), status_code=307
            )
        if should_serve_spa(normalized):
            return FileResponse(self.frontend_dir / "index.html")
        if response is not None:
            return response
        raise StarletteHTTPException(status_code=404)


def register_frontend_routes(app: FastAPI) -> None:
    frontend_server = FrontendServer()
    app.state.frontend_server = frontend_server

    if APP_CONTEXT_PATH:

        @app.get("/", include_in_schema=False)
        def app_root_redirect():
            return RedirectResponse(app_root_path(), status_code=307)

        @app.get(APP_CONTEXT_PATH, include_in_schema=False)
        def app_context_redirect():
            return RedirectResponse(app_root_path(), status_code=307)

    @app.get(RESET_PASSWORD_PATH)
    async def reset_password_page(request: Request):
        return await frontend_server.serve(request, "reset-password")

    @app.get(f"{RESET_PASSWORD_PATH}/")
    async def reset_password_page_slash(request: Request):
        return await frontend_server.serve(request, "reset-password/")

    @app.get(app_root_path(), include_in_schema=False)
    async def frontend_root(request: Request):
        return await frontend_server.serve(request, "")

    @app.get(
        f"{APP_CONTEXT_PATH}/{{frontend_path:path}}"
        if APP_CONTEXT_PATH
        else "/{frontend_path:path}",
        include_in_schema=False,
    )
    async def frontend_catchall(frontend_path: str, request: Request):
        return await frontend_server.serve(request, frontend_path)
