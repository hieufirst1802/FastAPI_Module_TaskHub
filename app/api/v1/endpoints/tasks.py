from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.repositories.task import TaskRepository
from app.schemas.pagination import PaginationParams
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])


def get_repository(request: Request) -> TaskRepository:
    repository: TaskRepository = request.app.state.repository
    return repository


Repository = Annotated[
    TaskRepository,
    Depends(get_repository),
]


def get_service(repository: Repository) -> TaskService:
    return TaskService(repository)


Service = Annotated[
    TaskService,
    Depends(get_service),
]


@router.post("", response_model=TaskOut, status_code=201)
def create(
    data: TaskCreate,
    repository: Repository,
) -> TaskOut:
    return repository.create(data)


@router.get("", response_model=list[TaskOut])
def page(
    repository: Repository,
    pagination: Annotated[PaginationParams, Depends()],
) -> list[TaskOut]:
    return repository.page(
        pagination.offset,
        pagination.limit,
    )


@router.get("/{identifier}", response_model=TaskOut)
def read(
    identifier: int,
    service: Service,
) -> TaskOut:
    return service.get(identifier)


@router.patch("/{identifier}", response_model=TaskOut)
def update(
    identifier: int,
    data: TaskUpdate,
    service: Service,
) -> TaskOut:
    return service.update(identifier, data)


@router.delete("/{identifier}", status_code=204)
def delete(
    identifier: int,
    service: Service,
) -> Response:
    service.delete(identifier)
    return Response(status_code=204)
