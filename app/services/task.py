
from app.models.task import Task
from app.models.user import User
from app.repositories.task import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, task_repository: TaskRepository) -> None:
        self.task_repository = task_repository

    async def create(self, data: TaskCreate, current_user: User) -> Task:
        return await self.task_repository.create(
            **data.model_dump(),
            owner_id=current_user.id,
        )

    async def page(
        self,
        offset: int,
        limit: int,
        current_user: User,
    ) -> tuple[list[Task], int]:
        if current_user.role == "admin":
            return await self.task_repository.page(offset, limit)

        return await self.task_repository.page(
            offset,
            limit,
            Task.owner_id == current_user.id,
        )

    async def get(
        self,
        identifier: int,
        current_user: User,
    ) -> Task | None:
        if current_user.role == "admin":
            return await self.task_repository.get(identifier)

        return await self.task_repository.get_by_owner(
            identifier,
            current_user.id,
        )

    async def update(
        self,
        identifier: int,
        data: TaskUpdate,
        current_user: User,
    ) -> Task | None:
        task = await self.get(identifier, current_user)

        if task is None:
            return None

        return await self.task_repository.update(
            task,
            data.model_dump(exclude_unset=True),
        )

    async def delete(
        self,
        identifier: int,
        current_user: User,
    ) -> bool:
        task = await self.get(identifier, current_user)

        if task is None:
            return False

        await self.task_repository.delete(task)
        return True
