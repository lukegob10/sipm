from __future__ import annotations

from fastapi import APIRouter

from .change_requests import router as change_requests_router
from .manifest import router as manifest_router
from .patches import router as patches_router
from .work_graph import router as work_graph_router

router = APIRouter(prefix="/agent", tags=["agent"])
router.include_router(manifest_router)
router.include_router(work_graph_router)
router.include_router(patches_router)
router.include_router(change_requests_router)
