from app.core.cache import TaskCache
from app.models.task import Task
from app.models.user import User
from app.repositories.task import TaskRepository
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.workspace import WorkspaceService


class TaskService:
    def __init__(self, task_repository: TaskRepository, cache: TaskCache | None = None) -> None:
        self.task_repository = task_repository
        self.cache = cache

    async def create(self, data: TaskCreate, current_user: User) -> Task:
        return await self.task_repository.create(
            **data.model_dump(),
            status="DONE" if data.completed else "TODO",
            owner_id=current_user.id,
        )

    async def page(
        self,
        offset: int,
        limit: int,
        current_user: User,
    ) -> tuple[list[Task], int]:
        if current_user.role == "admin":
            return await self.task_repository.page(offset, limit, Task.project_id.is_(None))

        return await self.task_repository.page(
            offset,
            limit,
            Task.owner_id == current_user.id,
            Task.project_id.is_(None),
        )

    async def _get_from_database(
        self,
        identifier: int,
        current_user: User,
    ) -> Task | None:
        if current_user.role == "admin":
            task = await self.task_repository.get(identifier)
        else:
            task = await self.task_repository.get_by_owner(identifier, current_user.id)
        if task is not None and task.project_id is not None:
            await WorkspaceService(self.task_repository.session, self.cache).project(
                task.project_id, current_user
            )
        return task

    async def get(self, identifier: int, current_user: User) -> Task | TaskOut | None:
        if self.cache is not None:
            cached = await self.cache.get(identifier)
            if cached is not None:
                if cached.project_id is not None:
                    await WorkspaceService(self.task_repository.session, self.cache).project(
                        cached.project_id, current_user
                    )
                if current_user.role == "admin" or cached.owner_id == current_user.id:
                    return cached
                return None
        task = await self._get_from_database(identifier, current_user)
        if task is not None and self.cache is not None:
            await self.cache.set(TaskOut.model_validate(task))
        return task

    async def update(
        self,
        identifier: int,
        data: TaskUpdate,
        current_user: User,
    ) -> Task | None:
        task = await self._get_from_database(identifier, current_user)

        if task is None:
            return None

        if task.project_id is not None:
            await WorkspaceService(self.task_repository.session, self.cache).project(
                task.project_id, current_user, write=True
            )
        values = data.model_dump(exclude_unset=True)
        if "completed" in values:
            values["status"] = "DONE" if values["completed"] else "TODO"
        updated = await self.task_repository.update(
            task,
            values,
        )

        if self.cache is not None:
            await self.cache.invalidate(identifier)
        if task.project_id is not None and self.cache is not None:
            await self.cache.invalidate_project(task.project_id)
        return updated

    async def delete(
        self,
        identifier: int,
        current_user: User,
    ) -> bool:
        task = await self._get_from_database(identifier, current_user)

        if task is None:
            return False

        if task.project_id is not None:
            await WorkspaceService(self.task_repository.session, self.cache).delete_task(
                identifier, current_user
            )
            return True
        await self.task_repository.delete(task)
        if self.cache is not None:
            await self.cache.invalidate(identifier)
        return True
