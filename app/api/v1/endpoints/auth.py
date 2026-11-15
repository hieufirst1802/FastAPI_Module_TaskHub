
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import Session
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service(session: Session) -> AuthService:
    return AuthService(session)


AuthServiceDependency = Annotated[
    AuthService,
    Depends(get_auth_service),
]

CurrentCredentials = Annotated[
    HTTPAuthorizationCredentials | None,
    Depends(bearer_scheme),
]


async def get_current_user(
    credentials: CurrentCredentials,
    session: Session,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        payload = decode_access_token(credentials.credentials)
        subject = payload.get("sub")

        if not isinstance(subject, str):
            raise unauthorized

        user_id = int(subject)
    except (jwt.InvalidTokenError, ValueError):
        raise unauthorized from None

    user = await UserRepository(session).get(user_id)

    if user is None:
        raise unauthorized

    return user


CurrentUser = Annotated[
    User,
    Depends(get_current_user),
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
