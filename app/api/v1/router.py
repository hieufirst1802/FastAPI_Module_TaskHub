from fastapi import APIRouter

from app.api.v1.endpoints import auth, tasks
from app.core.constants import API_V1_PREFIX

router = APIRouter(prefix=API_V1_PREFIX)
router.include_router(auth.router)
router.include_router(tasks.router)
