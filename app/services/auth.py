import hashlib
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.exceptions import UsernameAlreadyExistsError
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.users = UserRepository(session)
        self.session = session

    async def register(
        self,
        username: str,
        password: str,
        email: str | None = None,
        full_name: str = "",
    ) -> User:
        existing_user = await self.users.by_username(username)

        if existing_user is not None:
            raise UsernameAlreadyExistsError()

        try:
            user = await self.users.create(
                username=username,
                email=email,
                full_name=full_name,
                password_hash=hash_password(password),
                role="member",
            )
        except IntegrityError as exc:
            await self.session.rollback()
            if email is not None and "email" in str(exc.orig).lower():
                raise HTTPException(409, "Email already registered") from None
            raise UsernameAlreadyExistsError() from exc

        return user

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> User | None:
        user = await self.users.by_username(username)

        if user is None or not user.is_active:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    def create_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id), settings=self.settings)

    async def issue_tokens(self, user: User) -> TokenResponse:
        expires = datetime.now(UTC) + timedelta(days=self.settings.refresh_token_expire_days)
        refresh = jwt.encode(
            {"sub": str(user.id), "exp": expires, "type": "refresh", "jti": uuid4().hex},
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm,
        )
        self.session.add(
            RefreshToken(
                token_hash=hashlib.sha256(refresh.encode()).hexdigest(),
                user_id=user.id,
                expires_at=int(expires.timestamp()),
                revoked=False,
            )
        )
        await self.session.commit()
        return TokenResponse(access_token=self.create_token(user), refresh_token=refresh)

    async def refresh(self, token: str) -> TokenResponse:
        unauthorized = HTTPException(401, "Invalid or expired refresh token")
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm],
                options={"require": ["exp", "sub", "type", "jti"]},
            )
            if payload["type"] != "refresh":
                raise unauthorized
            user_id = int(payload["sub"])
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise unauthorized from None
        user = await self.users.get(user_id)
        if user is None or not user.is_active:
            raise unauthorized
        # Conditional UPDATE atomically consumes the refresh token, including concurrent requests.
        consumed = await self.session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.token_hash == hashlib.sha256(token.encode()).hexdigest(),
                RefreshToken.user_id == user_id,
                RefreshToken.revoked.is_(False),
                RefreshToken.expires_at > int(time.time()),
            )
            .values(revoked=True)
            .returning(RefreshToken.token_hash)
        )
        if consumed.scalar_one_or_none() is None:
            await self.session.rollback()
            raise unauthorized
        return await self.issue_tokens(user)

    async def logout(self, token: str) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hashlib.sha256(token.encode()).hexdigest())
            .values(revoked=True)
        )
        await self.session.commit()

    async def change_password(self, user: User, current: str, new: str) -> None:
        if not verify_password(current, user.password_hash):
            raise HTTPException(400, "Incorrect current password")
        user.password_hash = hash_password(new)
        await self.session.execute(
            update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
        )
        await self.session.commit()
