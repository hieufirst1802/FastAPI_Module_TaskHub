from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MIN_PAGE_SIZE
from app.enums import Priority, TaskStatus


class TaskFilters(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    search: str | None = Field(
        default=None, max_length=200, description="Substring in the title or description."
    )
    status: TaskStatus | None = None
    priority: Priority | None = None


class ProjectTaskFilters(TaskFilters):
    assignee_id: int | None = Field(default=None, gt=0, description="ID of the assigned account.")


class StandaloneTaskQuery(TaskFilters):
    completed: bool | None = Field(default=None, description="Filter by completion flag.")
    offset: int = Field(default=0, ge=0, description="Number of matching tasks to skip.")
    limit: int = Field(default=DEFAULT_PAGE_SIZE, ge=MIN_PAGE_SIZE, le=MAX_PAGE_SIZE)


class TaskCreate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    completed: bool = False


class TaskUpdate(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    completed: bool | None = None

    @model_validator(mode="after")
    def non_null(self) -> "TaskUpdate":
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Fields cannot be null; omit unchanged fields")
        return self


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    completed: bool
    project_id: int | None = None
    owner_id: int
