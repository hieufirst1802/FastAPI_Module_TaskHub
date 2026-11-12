from fastapi import HTTPException

from app.repositories import TaskRepository
from app.schemas import TaskOut, TaskUpdate


class TaskService:
    def __init__(self, repository: TaskRepository):
        self.repository = repository

    def get(self, identifier: int) -> TaskOut:
        row = self.repository.get(identifier)
        if row is None:
            raise HTTPException(404, "Task not found")
        return row

    def update(self, identifier: int, data: TaskUpdate) -> TaskOut:
        row = self.repository.update(identifier, data.model_dump(exclude_unset=True))
        if row is None:
            raise HTTPException(404, "Task not found")
        return row

    def delete(self, identifier: int) -> None:
        if not self.repository.delete(identifier):
            raise HTTPException(404, "Task not found")
