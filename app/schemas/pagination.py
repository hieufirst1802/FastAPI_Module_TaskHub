from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query

from app.core.constants import DEFAULT_LIMIT, DEFAULT_OFFSET, MAX_LIMIT, MIN_LIMIT
from app.schemas.base import BaseSchema


@dataclass(frozen=True)
class PaginationParams:
    offset: Annotated[int, Query(ge=DEFAULT_OFFSET)] = DEFAULT_OFFSET
    limit: Annotated[int, Query(ge=MIN_LIMIT, le=MAX_LIMIT)] = DEFAULT_LIMIT


Pagination = Annotated[PaginationParams, Depends()]


class Page[T](BaseSchema):
    items: list[T]
    total: int
    offset: int
    limit: int
