from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.database import Session
from app.core.dependencies import AppSettings, CurrentUser
from app.core.messages import INCORRECT_LOGIN, INVALID_AUTH_CREDENTIALS, USERNAME_ALREADY_REGISTERED
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(session: Session) -> AuthService:
    return AuthService(session)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an account",
    responses={
        409: {"description": USERNAME_ALREADY_REGISTERED},
        422: {"description": "Invalid registration data"},
    },
)
async def register(data: RegisterRequest, service: AuthServiceDependency) -> UserResponse:
    user = await service.register(data.username, data.password)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in and issue an access token",
    responses={
        401: {"description": INCORRECT_LOGIN},
        422: {"description": "Invalid login data"},
    },
)
async def login(
    data: LoginRequest, service: AuthServiceDependency, settings: AppSettings
) -> TokenResponse:
    user = await service.authenticate(data.username, data.password)
    return TokenResponse(access_token=create_access_token(str(user.id), settings))


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get the authenticated account",
    responses={401: {"description": INVALID_AUTH_CREDENTIALS}},
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
