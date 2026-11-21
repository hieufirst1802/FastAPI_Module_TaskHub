from app.core.cache import TaskCache
from app.core.exceptions import NotFoundException
from app.core.messages import TASK_NOT_FOUND
from app.enums import TaskStatus, UserRole
from app.models.task import Task
from app.models.user import User
from app.repositories.task import TaskRepository, task_filters
from app.schemas.pagination import TaskPage
from app.schemas.task import StandaloneTaskQuery, TaskCreate, TaskOut, TaskUpdate
from app.services.workspace import WorkspaceService


class TaskService:
    def __init__(
        self,
        task_repository: TaskRepository,
        workspace: WorkspaceService,
        cache: TaskCache | None = None,
    ) -> None:
        self.task_repository = task_repository
        self.workspace = workspace
        self.cache = cache

    async def create(self, data: TaskCreate, current_user: User) -> Task:
        task = await self.task_repository.create(
            **data.model_dump(),
            status=TaskStatus.DONE if data.completed else TaskStatus.TODO,
            owner_id=current_user.id,
        )
        if self.cache is not None:
            await self.cache.bump_version(self.cache.standalone_version_key())
        return task

    async def page(self, query: StandaloneTaskQuery, current_user: User) -> TaskPage:
        owner_id = None if current_user.role == UserRole.ADMIN else current_user.id
        cache = self.cache
        key = None
        if cache is not None:
            version = await cache.version(cache.standalone_version_key())
            if version is not None:
                key = cache.page_key(
                    "tasks:standalone",
                    version,
                    owner_id,
                    query.offset,
                    query.limit,
                    query.search or None,
                    query.status,
                    query.priority,
                    query.completed,
                )
                cached = await cache.get(key, TaskPage)
                if cached is not None:
                    return cached

        filters = task_filters(query)
        filters.append(Task.project_id.is_(None))
        if owner_id is not None:
            filters.append(Task.owner_id == owner_id)
        if query.completed is not None:
            filters.append(Task.completed == query.completed)
        rows, total = await self.task_repository.page(query.offset, query.limit, *filters)
        result = TaskPage(
            items=[TaskOut.model_validate(task) for task in rows],
            total=total,
            offset=query.offset,
            limit=query.limit,
        )
        if cache is not None and key is not None:
            await cache.set(key, result)
        return result

    async def _get_from_database(
        self,
        identifier: int,
        current_user: User,
    ) -> Task:
        if current_user.role == UserRole.ADMIN:
            task = await self.task_repository.get(identifier)
        else:
            task = await self.task_repository.get_by_owner(identifier, current_user.id)
        if task is None:
            raise NotFoundException(TASK_NOT_FOUND)
        if task.project_id is not None:
            try:
                await self.workspace.project(task.project_id, current_user)
            except NotFoundException as exc:
                raise NotFoundException(TASK_NOT_FOUND) from exc
        return task

    async def get(self, identifier: int, current_user: User) -> TaskOut:
        cache = self.cache
        key = None
        if cache is not None:
            version = await cache.version(cache.task_version_key(identifier))
            if version is not None:
                key = cache.task_detail_key(identifier, version)
                cached = await cache.get(key, TaskOut)
                if cached is not None and cached.id == identifier and cached.project_id is None:
                    if current_user.role == UserRole.ADMIN or cached.owner_id == current_user.id:
                        return cached
                    raise NotFoundException(TASK_NOT_FOUND)
        task = TaskOut.model_validate(await self._get_from_database(identifier, current_user))
        if cache is not None and key is not None and task.project_id is None:
            await cache.set(key, task)
        return task

    async def update(
        self,
        identifier: int,
        data: TaskUpdate,
        current_user: User,
    ) -> Task:
        task = await self._get_from_database(identifier, current_user)

        if task.project_id is not None:
            await self.workspace.project(task.project_id, current_user, write=True)
        values = data.model_dump(exclude_unset=True)
        if "completed" in values:
            values["status"] = TaskStatus.DONE if values["completed"] else TaskStatus.TODO
        updated = await self.task_repository.update(
            task,
            values,
        )

        if self.cache is not None:
            await self.cache.invalidate(identifier)
            if task.project_id is None:
                await self.cache.bump_version(self.cache.standalone_version_key())
            else:
                await self.cache.invalidate_project(task.project_id)
        return updated

    async def delete(
        self,
        identifier: int,
        current_user: User,
    ) -> None:
        task = await self._get_from_database(identifier, current_user)

        if task.project_id is not None:
            await self.workspace.delete_task(identifier, current_user)
            return
        await self.task_repository.delete(task)
        if self.cache is not None:
            await self.cache.invalidate(identifier)
            await self.cache.bump_version(self.cache.standalone_version_key())
