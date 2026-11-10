from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Task, User
from app.repositories import BaseRepository


class TaskService:
    def __init__(self, session: AsyncSession):
        self.repository = BaseRepository(session, Task)

    async def owned(self, identifier: int, user: User) -> Task:
        task = await self.repository.get(identifier)
        if task is None or (task.owner_id != user.id and user.role != "admin"):
            raise HTTPException(404, "Task not found")
        return task
