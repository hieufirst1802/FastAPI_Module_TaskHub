from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response

from app.repositories.task import TaskRepository
from app.schemas.pagination import PaginationParams, TaskPage
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


@router.post(
    "",
    response_model=TaskOut,
    status_code=201,
    summary="Create a task",
    responses={
        422: {"description": "Validation Error"},
    },
)
def create_task(
    data: TaskCreate,
    service: Service,
) -> TaskOut:
    return service.create(data)


@router.get(
    "",
    response_model=TaskPage,
    summary="List tasks",
    responses={
        422: {"description": "Validation Error"},
    },
)
def list_tasks(
    service: Service,
    pagination: Annotated[PaginationParams, Depends()],
) -> TaskPage:
    return service.page(pagination)


@router.get(
    "/{task_id}",
    response_model=TaskOut,
    summary="Get a task by ID",
    responses={
        404: {"description": "Task not found"},
        422: {"description": "Validation Error"},
    },
)
def get_task(
    task_id: Annotated[int, Path(gt=0)],
    service: Service,
) -> TaskOut:
    return service.get(task_id)


@router.patch(
    "/{task_id}",
    response_model=TaskOut,
    summary="Update a task",
    responses={
        404: {"description": "Task not found"},
        422: {"description": "Validation Error"},
    },
)
def update_task(
    task_id: Annotated[int, Path(gt=0)],
    data: TaskUpdate,
    service: Service,
) -> TaskOut:
    return service.update(task_id, data)


@router.delete(
    "/{task_id}",
    status_code=204,
    summary="Delete a task",
    responses={
        404: {"description": "Task not found"},
        422: {"description": "Validation Error"},
    },
)
def delete_task(
    task_id: Annotated[int, Path(gt=0)],
    service: Service,
) -> Response:
    service.delete(task_id)
    return Response(status_code=204)
