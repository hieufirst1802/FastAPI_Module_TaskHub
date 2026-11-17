from fastapi import APIRouter

from app.api.v1.endpoints import auth, health, tasks, users, workspaces
from app.schemas.auth import TokenResponse, UserResponse

router = APIRouter()

router.include_router(health.router)
router.include_router(auth.router)
router.include_router(tasks.router)
router.include_router(users.router)
router.include_router(workspaces.router)
# Keep existing URLs while exposing the documented versioned authentication API.
versioned_auth = APIRouter(prefix="/api/v1/auth", tags=["Authentication v1"])
versioned_auth.add_api_route(
    "/register", auth.register, methods=["POST"], response_model=UserResponse, status_code=201
)
versioned_auth.add_api_route("/login", auth.login, methods=["POST"], response_model=TokenResponse)
versioned_auth.add_api_route(
    "/refresh", auth.refresh, methods=["POST"], response_model=TokenResponse
)
versioned_auth.add_api_route("/logout", auth.logout, methods=["POST"], status_code=204)
versioned_auth.add_api_route(
    "/change-password", auth.change_password, methods=["POST"], status_code=204
)
router.include_router(versioned_auth)
