from typing import Annotated, cast

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import Settings
from app.core.database import Session
from app.core.exceptions import UnauthorizedException
from app.core.messages import INVALID_AUTH_CREDENTIALS
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository

Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(HTTPBearer(auto_error=False))]


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


AppSettings = Annotated[Settings, Depends(get_app_settings)]


async def get_current_user(
    credentials: Credentials, session: Session, settings: AppSettings
) -> User:
    if credentials is None:
        raise UnauthorizedException(INVALID_AUTH_CREDENTIALS)

    try:
        user_id = decode_access_token(credentials.credentials, settings)
    except (jwt.InvalidTokenError, ValueError, TypeError, OverflowError) as exc:
        raise UnauthorizedException(INVALID_AUTH_CREDENTIALS) from exc

    user = await UserRepository(session).get(user_id)
    if user is None or not user.is_active:
        raise UnauthorizedException(INVALID_AUTH_CREDENTIALS)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
