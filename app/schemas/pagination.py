from pydantic import BaseModel, Field

from app.core.constants import (
    DEFAULT_PAGE_LIMIT,
    DEFAULT_PAGE_OFFSET,
    MAX_PAGE_LIMIT,
)


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