from fastapi import APIRouter, Depends

from ..deps import require_user
from .audit import router as audit_router
from .auth import router as auth_router
from .projects import router as projects_router
from .phases import router as phases_router
from .solutions import router as solutions_router
from .subcomponents import router as subcomponents_router
from .sync import router as sync_router
from .spaces import router as spaces_router
from .teams import router as teams_router
from .users import router as users_router
from .planning import router as planning_router

api_router = APIRouter()
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])

protected_router = APIRouter(dependencies=[Depends(require_user)])
protected_router.include_router(projects_router, prefix="/projects", tags=["projects"])
protected_router.include_router(solutions_router, tags=["solutions"])
protected_router.include_router(phases_router, tags=["phases"])
protected_router.include_router(subcomponents_router, tags=["subcomponents"])
protected_router.include_router(teams_router, tags=["teams"])
protected_router.include_router(spaces_router, tags=["spaces"])
protected_router.include_router(users_router, tags=["users"])
protected_router.include_router(planning_router, tags=["planning"])
protected_router.include_router(audit_router, tags=["audit"])

api_router.include_router(protected_router)
api_router.include_router(sync_router, tags=["sync"])
