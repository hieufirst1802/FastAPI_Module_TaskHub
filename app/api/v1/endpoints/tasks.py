from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from app.core.database import Session
from app.core.dependencies import CurrentUser
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.pagination import TaskPage
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task import TaskService

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def get_task_service(session: Session, request: Request) -> TaskService:
    task_repository = TaskRepository(session)

    return TaskService(task_repository, request.app.state.task_cache)


def to_task_out(task: Task | TaskOut) -> TaskOut:
    return TaskOut.model_validate(task)


TaskServiceDependency = Annotated[
    TaskService,
    Depends(get_task_service),
]


@router.post("", response_model=TaskOut, status_code=201)
async def create(
    data: TaskCreate,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> TaskOut:
    task = await service.create(data, current_user)
    return to_task_out(task)


@router.get("", response_model=TaskPage)
async def page(
    service: TaskServiceDependency,
    current_user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TaskPage:
    rows, total = await service.page(offset, limit, current_user)

    return TaskPage(
        items=[to_task_out(task) for task in rows],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{identifier}", response_model=TaskOut)
async def read(
    identifier: int,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> TaskOut:
    task = await service.get(identifier, current_user)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return to_task_out(task)


@router.patch("/{identifier}", response_model=TaskOut)
async def update(
    identifier: int,
    data: TaskUpdate,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> TaskOut:
    task = await service.update(identifier, data, current_user)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return to_task_out(task)


@router.delete("/{identifier}", status_code=204)
async def delete(
    identifier: int,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> Response:
    deleted = await service.delete(identifier, current_user)

    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    return Response(status_code=204)
