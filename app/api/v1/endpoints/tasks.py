from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

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
    service: Service,
) -> TaskOut:
    return service.create(data)


@router.get("", response_model=list[TaskOut])
def page(
    service: Service,
    pagination: Annotated[PaginationParams, Depends()],
) -> list[TaskOut]:
    return service.page(pagination)


@router.get("/{task_id}", response_model=TaskOut)
def read(
    task_id: Annotated[int, Path(gt=0)],
    service: Service,
) -> TaskOut:
    return service.get(task_id)


@router.patch("/{task_id}", response_model=TaskOut)
def update(
    task_id: Annotated[int, Path(gt=0)],
    data: TaskUpdate,
    service: Service,
) -> TaskOut:
    return service.update(task_id, data)


@router.delete("/{task_id}", status_code=204)
def delete(
    task_id: Annotated[int, Path(gt=0)],
    service: Service,
) -> Response:
    service.delete(task_id)
    return Response(status_code=204)
