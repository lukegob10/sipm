from __future__ import annotations

from fastapi import FastAPI

from backend.app.frontend import register_frontend_routes
from backend.app.health import register_health_routes
from backend.app.lifespan import lifespan
from backend.app.middleware import register_observability_middleware
from backend.app.paths import API_PREFIX, DOCS_PATH, OPENAPI_PATH, REDOC_PATH
from backend.app.routes import api_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="SIPM API",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=OPENAPI_PATH,
        docs_url=DOCS_PATH,
        redoc_url=REDOC_PATH,
    )
    app.include_router(api_router, prefix=API_PREFIX)
    register_observability_middleware(app)
    register_health_routes(app)
    register_frontend_routes(app)
    return app


app = create_app()
