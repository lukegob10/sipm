from fastapi import APIRouter

from . import common as _common
from .import_export import router as import_export_router
from .read import router as read_router
from .write import router as write_router

router = APIRouter()
router.include_router(import_export_router)
router.include_router(read_router)
router.include_router(write_router)

# Preserve the package-level monkeypatch target used by the current tests.
enable_all_phases = _common.enable_all_phases

__all__ = ["router", "enable_all_phases"]
