from pydantic import Field, model_validator

from app.core.constants import TITLE_MAX_LENGTH, TITLE_MIN_LENGTH
from app.core.messages import TASK_NULL_UPDATE
from app.schemas.base import BaseSchema


class TaskBase(BaseSchema):
    title: str = Field(
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
    )
    completed: bool = False


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseSchema):
    title: str | None = Field(
        default=None,
        min_length=TITLE_MIN_LENGTH,
        max_length=TITLE_MAX_LENGTH,
    )
    completed: bool | None = None

    @model_validator(mode="after")
    def non_null(self) -> "TaskUpdate":
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError(TASK_NULL_UPDATE)

        return self


class TaskOut(TaskBase):
    id: int
