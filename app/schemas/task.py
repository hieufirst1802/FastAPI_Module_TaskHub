from typing import Annotated, Self

from pydantic import Field, model_validator

from app.core.constants import DESCRIPTION_MAX_LENGTH, TITLE_MAX_LENGTH, TITLE_MIN_LENGTH
from app.core.messages import NULL_UPDATE_FIELDS
from app.models.enums import TaskStatus
from app.schemas.base import BaseSchema

TaskTitle = Annotated[str, Field(min_length=TITLE_MIN_LENGTH, max_length=TITLE_MAX_LENGTH)]
TaskDescription = Annotated[str, Field(max_length=DESCRIPTION_MAX_LENGTH)]


class TaskBase(BaseSchema):
    title: TaskTitle
    description: TaskDescription = ""
    status: TaskStatus = TaskStatus.TODO


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseSchema):
    title: TaskTitle | None = None
    description: TaskDescription | None = None
    status: TaskStatus | None = None

    @model_validator(mode="after")
    def non_null(self) -> Self:
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError(NULL_UPDATE_FIELDS)
        return self


class TaskOut(TaskBase):
    id: int
    owner_id: int
