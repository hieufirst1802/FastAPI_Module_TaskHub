from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Response, status

from app.core.database import Session
from app.core.messages import DEMO_OWNER_NOT_FOUND, TASK_NOT_FOUND
from app.repositories.task import TaskRepository
from app.repositories.user import UserRepository
from app.schemas.pagination import Page, Pagination
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task import TaskService

router = APIRouter(prefix="/tasks", tags=["Tasks"])

TaskId = Annotated[int, Path(gt=0)]
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": TASK_NOT_FOUND},
}


def get_task_service(session: Session) -> TaskService:
    return TaskService(session, TaskRepository(session), UserRepository(session))


TaskServiceDependency = Annotated[TaskService, Depends(get_task_service)]


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
    responses={404: {"description": DEMO_OWNER_NOT_FOUND}},
)
async def create_task(data: TaskCreate, service: TaskServiceDependency) -> TaskOut:
    return TaskOut.model_validate(await service.create(data))


@router.get("", response_model=Page[TaskOut], summary="List tasks")
async def list_tasks(service: TaskServiceDependency, pagination: Pagination) -> Page[TaskOut]:
    rows, total = await service.page(pagination)
    return Page[TaskOut](
        items=[TaskOut.model_validate(task) for task in rows],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get(
    "/{task_id}", response_model=TaskOut, summary="Get a task", responses=NOT_FOUND_RESPONSE
)
async def get_task(task_id: TaskId, service: TaskServiceDependency) -> TaskOut:
    return TaskOut.model_validate(await service.get(task_id))


@router.patch(
    "/{task_id}", response_model=TaskOut, summary="Update a task", responses=NOT_FOUND_RESPONSE
)
async def update_task(task_id: TaskId, data: TaskUpdate, service: TaskServiceDependency) -> TaskOut:
    return TaskOut.model_validate(await service.update(task_id, data))


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    responses=NOT_FOUND_RESPONSE,
)
async def delete_task(task_id: TaskId, service: TaskServiceDependency) -> Response:
    await service.delete(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
