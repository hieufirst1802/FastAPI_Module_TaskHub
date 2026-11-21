from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEMO_USERNAME
from app.core.exceptions import NotFoundException
from app.core.messages import DEMO_OWNER_NOT_FOUND, TASK_NOT_FOUND
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(
        self,
        session: AsyncSession,
        task_repository: TaskRepository,
        user_repository: UserRepository,
    ) -> None:
        self.session = session
        self.task_repository = task_repository
        self.user_repository = user_repository

    async def create(self, data: TaskCreate) -> Task:
        async with self.session.begin():
            owner = await self.user_repository.by_username(DEMO_USERNAME)
            if owner is None:
                raise NotFoundException(DEMO_OWNER_NOT_FOUND)

            return await self.task_repository.create(**data.model_dump(), owner_id=owner.id)

    async def page(self, pagination: PaginationParams) -> tuple[list[Task], int]:
        return await self.task_repository.page(pagination)

    async def get(self, task_id: int) -> Task:
        task = await self.task_repository.get(task_id)
        if task is None:
            raise NotFoundException(TASK_NOT_FOUND)
        return task

    async def update(self, task_id: int, data: TaskUpdate) -> Task:
        async with self.session.begin():
            task = await self.get(task_id)
            return await self.task_repository.update(task, data.model_dump(exclude_unset=True))

    async def delete(self, task_id: int) -> None:
        async with self.session.begin():
            task = await self.get(task_id)
            await self.task_repository.delete(task)
