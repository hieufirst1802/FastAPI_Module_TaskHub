from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import transaction
from app.core.exceptions import NotFoundException
from app.core.messages import TASK_NOT_FOUND
from app.models.task import Task
from app.models.user import User
from app.repositories.task import TaskRepository
from app.schemas.pagination import PaginationParams
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.task_repository = TaskRepository(session)

    async def create(self, data: TaskCreate, current_user: User) -> Task:
        async with transaction(self.session):
            return await self.task_repository.create(**data.model_dump(), owner_id=current_user.id)

    async def page(self, pagination: PaginationParams, owner_id: int) -> tuple[list[Task], int]:
        return await self.task_repository.page(pagination, Task.owner_id == owner_id)

    async def get(self, task_id: int, owner_id: int) -> Task:
        task = await self.task_repository.get(task_id)
        if task is None or task.owner_id != owner_id:
            raise NotFoundException(TASK_NOT_FOUND)
        return task

    async def update(self, task_id: int, data: TaskUpdate, owner_id: int) -> Task:
        async with transaction(self.session):
            task = await self.get(task_id, owner_id)
            return await self.task_repository.update(task, data.model_dump(exclude_unset=True))

    async def delete(self, task_id: int, owner_id: int) -> None:
        async with transaction(self.session):
            task = await self.get(task_id, owner_id)
            await self.task_repository.delete(task)
