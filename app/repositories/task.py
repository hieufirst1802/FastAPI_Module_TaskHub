from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models.task import Task
from app.repositories.base import BaseRepository
from app.schemas.task import TaskFilters


def task_filters(query: TaskFilters) -> list[ColumnElement[bool]]:
    filters: list[ColumnElement[bool]] = []
    if query.search:
        filters.append(
            or_(
                Task.title.icontains(query.search, autoescape=True),
                Task.description.icontains(query.search, autoescape=True),
            )
        )
    if query.status is not None:
        filters.append(Task.status == query.status)
    if query.priority is not None:
        filters.append(Task.priority == query.priority)
    return filters


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
