from fastapi import APIRouter

from .legacy_allocations import router as legacy_allocations_router
from .work_allocation import router as work_allocation_router


router = APIRouter()
router.include_router(legacy_allocations_router)
router.include_router(work_allocation_router)
