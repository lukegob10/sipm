from typing import List

from fastapi import APIRouter, status

from . import common as _common
from .import_export import router as import_export_router
from .read import list_projects, router as read_router
from .write import create_project, router as write_router
from ...schemas import ProjectRead

router = APIRouter(prefix="/projects")
router.add_api_route(
    "", list_projects, methods=["GET"], response_model=List[ProjectRead]
)
router.add_api_route(
    "/", list_projects, methods=["GET"], response_model=List[ProjectRead]
)
router.add_api_route(
    "",
    create_project,
    methods=["POST"],
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
router.add_api_route(
    "/",
    create_project,
    methods=["POST"],
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
)
router.include_router(import_export_router)
router.include_router(read_router)
router.include_router(write_router)

# Preserve the package-level helper target used by the current tests.
_is_project_name_conflict_integrity_error = (
    _common._is_project_name_conflict_integrity_error
)

__all__ = ["router", "_is_project_name_conflict_integrity_error"]
