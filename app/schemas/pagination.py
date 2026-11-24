from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_PAGE_SIZE, FIRST_PAGE, MAX_PAGE_SIZE, MIN_PAGE_SIZE
from app.schemas.auth import UserResponse
from app.schemas.task import TaskOut


class TaskPage(BaseModel):
    items: list[TaskOut]
    total: int = Field(description="Number of matching tasks before pagination.")
    offset: int
    limit: int


class UserPage(BaseModel):
    items: list[UserResponse]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True)
class PaginationParams:
    page: Annotated[int, Query(ge=FIRST_PAGE)] = FIRST_PAGE
    limit: Annotated[int, Query(ge=MIN_PAGE_SIZE, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE

    @property
    def offset(self) -> int:
        return (self.page - FIRST_PAGE) * self.limit


PaginationDep = Annotated[PaginationParams, Depends()]


class Page[T](BaseModel):
    items: list[T]
    total: int = Field(description="Number of matching records before pagination.")
    page: int
    limit: int
