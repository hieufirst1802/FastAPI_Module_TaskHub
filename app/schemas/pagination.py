from pydantic import BaseModel

from app.schemas.task import TaskOut


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    offset: int
    limit: int
