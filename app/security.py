from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from pwdlib import PasswordHash

from app.database import Session
from app.models import User
from app.repositories import UserRepository

passwords = PasswordHash.recommended()
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def issue_token(user: User, secret: str, minutes: int) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=minutes)},
        secret,
        algorithm="HS256",
    )


async def get_current_user(
    request: Request, session: Session, token: Annotated[str, Depends(oauth2)]
) -> User:
    error = HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(
            token,
            request.app.state.settings.jwt_secret,
            algorithms=["HS256"],
            options={"require": ["sub", "exp", "iat"]},
        )
        identifier = int(payload["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise error from None
    user = await UserRepository(session).get(identifier)
    if user is None:
        raise error
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise HTTPException(403, "Administrator required")
    return user


Admin = Annotated[User, Depends(require_admin)]
