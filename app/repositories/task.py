
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, Task)

    async def get_by_owner(
        self,
        identifier: int,
        owner_id: int,
    ) -> Task | None:
        statement = select(Task).where(
            Task.id == identifier,
            Task.owner_id == owner_id,
        )
        return await self.session.scalar(statement)
