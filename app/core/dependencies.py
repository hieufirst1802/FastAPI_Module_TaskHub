
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from app.core.database import Session
from app.core.security import decode_access_token
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

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
