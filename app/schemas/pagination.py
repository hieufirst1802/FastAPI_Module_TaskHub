from pydantic import BaseModel, Field

from app.core.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    MAX_PAGE_LIMIT,
)
from app.schemas.base import BaseSchema
from app.schemas.task import TaskOut


class PaginationParams(BaseModel):
    offset: int = Field(
        default=DEFAULT_PAGE_OFFSET,
        ge=0,
    )
    limit: int = Field(
        default=DEFAULT_PAGE_LIMIT,
        ge=1,
        le=MAX_PAGE_LIMIT,
    )


class TaskPage(BaseSchema):
    items: list[TaskOut]
    total: int = Field(ge=0)
    offset: int = Field(ge=0)
    limit: int = Field(ge=1)
