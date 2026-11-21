from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status

from app.core.api_docs import error_responses
from app.core.database import Session
from app.core.dependencies import CurrentUser
from app.core.exceptions import UnauthorizedException
from app.core.messages import INCORRECT_LOGIN
from app.schemas.auth import (
    LoginRequest,
    PasswordChange,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(session: Session, request: Request) -> AuthService:
    return AuthService(session, request.app.state.settings)


AuthServiceDependency = Annotated[
    AuthService,
    Depends(get_auth_service),
]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register an account",
    description="Create a member account using a unique username and optional email.",
    responses=error_responses(409, 422),
)
async def register(
    data: RegisterRequest,
    service: AuthServiceDependency,
) -> UserResponse:
    user = await service.register(
        username=data.username,
        password=data.password,
        email=data.email,
        full_name=data.full_name,
    )
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in",
    description="Exchange the username and password for an access token and a refresh token.",
    responses=error_responses(401, 422),
)
async def login(
    data: LoginRequest,
    service: AuthServiceDependency,
) -> TokenResponse:
    user = await service.authenticate(
        username=data.username,
        password=data.password,
    )

    if user is None:
        raise UnauthorizedException(INCORRECT_LOGIN)

    return await service.issue_tokens(user)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Read the signed-in account",
    description="Return the account associated with the Bearer access token.",
    responses=error_responses(401),
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate the refresh token",
    description="Exchange the current refresh token for a new token pair. The supplied token is consumed on success.",
    responses=error_responses(401, 422),
)
async def refresh(data: RefreshRequest, service: AuthServiceDependency) -> TokenResponse:
    return await service.refresh(data.refresh_token)


@router.post(
    "/logout",
    status_code=204,
    summary="Revoke a refresh token",
    description="Revoke the supplied refresh token. The response has no body.",
    responses=error_responses(401, 422),
)
async def logout(data: RefreshRequest, service: AuthServiceDependency) -> Response:
    await service.logout(data.refresh_token)
    return Response(status_code=204)


@router.post(
    "/change-password",
    status_code=204,
    summary="Change the account password",
    description="Verify the current password and revoke existing refresh tokens after changing it.",
    responses=error_responses(400, 401, 422),
)
async def change_password(
    data: PasswordChange, user: CurrentUser, service: AuthServiceDependency
) -> Response:
    await service.change_password(user, data.current_password, data.new_password)
    return Response(status_code=204)
