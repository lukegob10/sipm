from __future__ import annotations

from fastapi import APIRouter

from ...schemas.agent import AgentErrorRead
from .change_requests import router as change_requests_router
from .manifest import router as manifest_router
from .patches import router as patches_router
from .programs import router as programs_router
from .spaces import router as spaces_router
from .work_graph import router as work_graph_router
from .work_items import router as work_items_router
from .work_search import router as work_search_router
from .discovery import router as discovery_router
from .people import router as people_router

_ERROR_RESPONSES = {
    status_code: {"model": AgentErrorRead}
    for status_code in (400, 401, 403, 404, 405, 409, 413, 422, 429)
}

router = APIRouter(
    prefix="/agent",
    tags=["agent"],
    responses=_ERROR_RESPONSES,
)
router.include_router(manifest_router)
router.include_router(spaces_router)
router.include_router(work_graph_router)
router.include_router(programs_router)
router.include_router(work_items_router)
router.include_router(work_search_router)
router.include_router(discovery_router)
router.include_router(people_router)
router.include_router(patches_router)
router.include_router(change_requests_router)
