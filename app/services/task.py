from app.core.exceptions import NotFoundException
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.pagination import PaginationParams, TaskPage
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    @staticmethod
    def _to_schema(task: Task) -> TaskOut:
        return TaskOut(
            id=task.id,
            title=task.title,
            completed=task.completed,
        )

    def create(self, data: TaskCreate) -> TaskOut:
        task = self.repository.create(data.model_dump())
        return self._to_schema(task)

    def page(self, pagination: PaginationParams) -> TaskPage:
        tasks = self.repository.page(
            pagination.offset,
            pagination.limit,
        )

        return TaskPage(
            items=[self._to_schema(task) for task in tasks],
            total=self.repository.count(),
            offset=pagination.offset,
            limit=pagination.limit,
        )

    def get(self, task_id: int) -> TaskOut:
        task = self.repository.get(task_id)

        if task is None:
            raise NotFoundException(task_id)

        return self._to_schema(task)

    def update(
        self,
        task_id: int,
        data: TaskUpdate,
    ) -> TaskOut:
        task = self.repository.update(
            task_id,
            data.model_dump(exclude_unset=True),
        )

        if task is None:
            raise NotFoundException(task_id)

        return self._to_schema(task)

    def delete(self, task_id: int) -> None:
        if not self.repository.delete(task_id):
            raise NotFoundException(task_id)
