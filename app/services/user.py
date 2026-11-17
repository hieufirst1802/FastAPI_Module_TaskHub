from app.models.user import User
from app.repositories.user import UserRepository


class UserService:
    def __init__(self, user_repository: UserRepository) -> None:
        self.user_repository = user_repository

    async def page(
        self,
        offset: int,
        limit: int,
    ) -> tuple[list[User], int]:
        return await self.user_repository.page(offset, limit)
