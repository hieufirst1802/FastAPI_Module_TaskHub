from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.task import Task
from app.repositories.base import BaseRepository


def task_search_filters(search: str | None) -> list[ColumnElement[bool]]:
    if not search:
        return []
    return [
        or_(
            Task.title.icontains(search, autoescape=True),
            Task.description.icontains(search, autoescape=True),
        )
    ]


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
