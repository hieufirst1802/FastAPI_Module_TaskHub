from fastapi import APIRouter

from app.api.v1.endpoints import health, tasks
from app.core.constants import API_PREFIX

router = APIRouter()

router.include_router(health.router)
router.include_router(
    tasks.router,
    prefix=API_PREFIX,
)