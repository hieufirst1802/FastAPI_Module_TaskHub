from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.database import transaction
from app.core.exceptions import UnauthorizedException, UsernameAlreadyExistsError
from app.core.messages import INCORRECT_LOGIN
from app.core.security import DUMMY_HASH, hash_password, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.user import UserRepository


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.users = UserRepository(session)
        self.session = session

    async def register(self, username: str, password: str) -> User:
        hashed_password = await run_in_threadpool(hash_password, password)

        try:
            async with transaction(self.session):
                return await self.users.create(
                    username=username, password_hash=hashed_password, role=UserRole.MEMBER
                )
        except IntegrityError as exc:
            if await self.users.by_username(username) is not None:
                raise UsernameAlreadyExistsError() from exc
            raise

    async def authenticate(self, username: str, password: str) -> User:
        user = await self.users.by_username(username)
        stored_hash = user.password_hash if user and user.is_active else DUMMY_HASH
        valid_password = await run_in_threadpool(verify_password, password, stored_hash)
        if user is None or not user.is_active or not valid_password:
            raise UnauthorizedException(INCORRECT_LOGIN)
        return user
