
from pydantic import BaseModel

from app.schemas.auth import UserResponse
from app.schemas.task import TaskOut


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int
    offset: int
    limit: int


class UserPage(BaseModel):
    items: list[UserResponse]
    total: int
    offset: int
    limit: int
