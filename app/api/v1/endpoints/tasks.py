from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response

from app.core.database import Session
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.schemas.pagination import TaskPage
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task import TaskService

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def get_task_service(session: Session) -> TaskService:
    task_repository = TaskRepository(session)
    user_repository = UserRepository(session)

    return TaskService(task_repository, user_repository)


def to_task_out(task: Task) -> TaskOut:
    return TaskOut.model_validate(task)


TaskServiceDependency = Annotated[
    TaskService,
    Depends(get_task_service),
]


@router.post("", response_model=TaskOut, status_code=201)
async def create(
    data: TaskCreate,
    service: TaskServiceDependency,
) -> TaskOut:
    task = await service.create(data)
    return to_task_out(task)


@router.get("", response_model=TaskPage)
async def page(
    service: TaskServiceDependency,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TaskPage:
    rows, total = await service.page(offset, limit)

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
) -> TaskOut:
    task = await service.get(identifier)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return to_task_out(task)


@router.patch("/{identifier}", response_model=TaskOut)
async def update(
    identifier: int,
    data: TaskUpdate,
    service: TaskServiceDependency,
) -> TaskOut:
    task = await service.update(identifier, data)

    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")

    return to_task_out(task)


@router.delete("/{identifier}", status_code=204)
async def delete(
    identifier: int,
    service: TaskServiceDependency,
) -> Response:
    deleted = await service.delete(identifier)

    if not deleted:
        raise HTTPException(status_code=404, detail="Task not found")

    return Response(status_code=204)
