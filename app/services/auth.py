
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.session = session

    async def register(
        self,
        username: str,
        password: str,
    ) -> User:
        existing_user = await self.users.by_username(username)

        if existing_user is not None:
            raise ValueError("Username already registered")

        try:
            user = await self.users.create(
                username=username,
                password_hash=hash_password(password),
                role="member",
            )
        except IntegrityError as exc:
            await self.session.rollback()
            raise ValueError("Username already registered") from exc

        return user

    async def authenticate(
        self,
        username: str,
        password: str,
    ) -> User | None:
        user = await self.users.by_username(username)

        if user is None:
            return None

        if not verify_password(password, user.password_hash):
            return None

        return user

    def create_token(self, user: User) -> str:
        return create_access_token(subject=str(user.id))
