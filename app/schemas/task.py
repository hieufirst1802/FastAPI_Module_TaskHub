from pydantic import Field, model_validator

from app.schemas.base import BaseSchema


class TaskCreate(BaseSchema):
    title: str = Field(min_length=1, max_length=200)
    completed: bool = False


class TaskUpdate(BaseSchema):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    completed: bool | None = None

    @model_validator(mode="after")
    def non_null(self) -> "TaskUpdate":
        if any(
            getattr(self, name) is None
            for name in self.model_fields_set
        ):
            raise ValueError(
                "Omit unchanged fields; null is not allowed"
            )
        return self


class TaskOut(TaskCreate):
    id: int