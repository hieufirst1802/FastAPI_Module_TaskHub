from app.core.exceptions import TaskNotFoundError
from app.repositories.task import TaskRepository
from app.schemas.task import TaskOut, TaskUpdate


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def get(self, identifier: int) -> TaskOut:
        row = self.repository.get(identifier)

        if row is None:
            raise TaskNotFoundError(identifier)

        return row

    def update(
        self,
        identifier: int,
        data: TaskUpdate,
    ) -> TaskOut:
        row = self.repository.update(
            identifier,
            data.model_dump(exclude_unset=True),
        )

        if row is None:
            raise TaskNotFoundError(identifier)

        return row

    def delete(self, identifier: int) -> None:
        if not self.repository.delete(identifier):
            raise TaskNotFoundError(identifier)