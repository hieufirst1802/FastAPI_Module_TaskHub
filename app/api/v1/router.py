from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, tasks, users, workspaces
from app.core.constants import API_V1_PREFIX

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router, prefix=API_V1_PREFIX)
router.include_router(tasks.router)
router.include_router(users.router)
router.include_router(workspaces.router)
