from app.models.task import Task
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(
        self,
        task_repository: TaskRepository,
        user_repository: UserRepository,
    ) -> None:
        self.task_repository = task_repository
        self.user_repository = user_repository

    async def create(self, data: TaskCreate) -> Task:
        owner = await self.user_repository.by_username("demo")

        if owner is None:
            owner = await self.user_repository.create(
                username="demo",
                password_hash="disabled-login",
            )

        return await self.task_repository.create(
            **data.model_dump(),
            owner_id=owner.id,
        )

    async def page(self, offset: int, limit: int) -> tuple[list[Task], int]:
        return await self.task_repository.page(offset, limit)

    async def get(self, identifier: int) -> Task | None:
        return await self.task_repository.get(identifier)

    async def update(
        self,
        identifier: int,
        data: TaskUpdate,
    ) -> Task | None:
        task = await self.task_repository.get(identifier)

        if task is None:
            return None

        return await self.task_repository.update(
            task,
            data.model_dump(exclude_unset=True),
        )

    async def delete(self, identifier: int) -> bool:
        task = await self.task_repository.get(identifier)

        if task is None:
            return False

        await self.task_repository.delete(task)
        return True
