
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import Session
from app.core.dependencies import CurrentUser
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def get_auth_service(session: Session) -> AuthService:
    return AuthService(session)


AuthServiceDependency = Annotated[
    AuthService,
    Depends(get_auth_service),
]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    data: RegisterRequest,
    service: AuthServiceDependency,
) -> UserResponse:
    try:
        user = await service.register(
            username=data.username,
            password=data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
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
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=service.create_token(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)
