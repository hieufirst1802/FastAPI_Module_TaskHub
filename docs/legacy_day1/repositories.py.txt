from threading import RLock
from typing import Any

from app.schemas import TaskCreate, TaskOut


class TaskRepository:
    def __init__(self) -> None:
        self.rows: dict[int, TaskOut] = {}
        self.next_id = 1
        self.lock = RLock()

    def create(self, data: TaskCreate) -> TaskOut:
        with self.lock:
            row = TaskOut(id=self.next_id, **data.model_dump())
            self.next_id += 1
            self.rows[row.id] = row
            return row

    def get(self, identifier: int) -> TaskOut | None:
        with self.lock:
            return self.rows.get(identifier)

    def page(self, offset: int, limit: int) -> list[TaskOut]:
        with self.lock:
            return list(self.rows.values())[offset : offset + limit]

    def update(self, identifier: int, values: dict[str, Any]) -> TaskOut | None:
        with self.lock:
            row = self.rows.get(identifier)
            if row is None:
                return None
            updated = TaskOut.model_validate(row.model_dump() | values)
            self.rows[identifier] = updated
            return updated

    def delete(self, identifier: int) -> bool:
        with self.lock:
            return self.rows.pop(identifier, None) is not None
