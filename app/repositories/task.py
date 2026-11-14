from threading import RLock
from typing import Any

from app.models.task import Task


class TaskRepository:
    def __init__(self) -> None:
        self.rows: dict[int, Task] = {}
        self.next_id = 1
        self.lock = RLock()

    def create(self, values: dict[str, Any]) -> Task:
        with self.lock:
            row = Task(
                id=self.next_id,
                **values,
            )

            self.next_id += 1
            self.rows[row.id] = row

            return row

    def get(self, identifier: int) -> Task | None:
        with self.lock:
            return self.rows.get(identifier)

    def page(
        self,
        offset: int,
        limit: int,
    ) -> list[Task]:
        with self.lock:
            return list(self.rows.values())[offset : offset + limit]

    def update(
        self,
        identifier: int,
        values: dict[str, Any],
    ) -> Task | None:
        with self.lock:
            row = self.rows.get(identifier)

            if row is None:
                return None

            updated = Task(
                id=row.id,
                title=values.get("title", row.title),
                completed=values.get("completed", row.completed),
            )

            self.rows[identifier] = updated

            return updated

    def delete(self, identifier: int) -> bool:
        with self.lock:
            return self.rows.pop(identifier, None) is not None
