from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Response, status

from app.core.database import Session
from app.core.dependencies import CurrentUser
from app.core.messages import INVALID_AUTH_CREDENTIALS, TASK_NOT_FOUND
from app.schemas.pagination import Page, Pagination
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services.task import TaskService

router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
    responses={status.HTTP_401_UNAUTHORIZED: {"description": INVALID_AUTH_CREDENTIALS}},
)

TaskId = Annotated[int, Path(gt=0)]
NOT_FOUND_RESPONSE: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {"description": TASK_NOT_FOUND},
}


def get_task_service(session: Session) -> TaskService:
    return TaskService(session)


TaskServiceDependency = Annotated[TaskService, Depends(get_task_service)]


@router.post(
    "",
    response_model=TaskOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
async def create_task(
    data: TaskCreate, service: TaskServiceDependency, user: CurrentUser
) -> TaskOut:
    return TaskOut.model_validate(await service.create(data, user))


@router.get("", response_model=Page[TaskOut], summary="List tasks")
async def list_tasks(
    service: TaskServiceDependency, pagination: Pagination, user: CurrentUser
) -> Page[TaskOut]:
    rows, total = await service.page(pagination, user.id)
    return Page[TaskOut](
        items=[TaskOut.model_validate(task) for task in rows],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )


@router.get(
    "/{task_id}", response_model=TaskOut, summary="Get a task", responses=NOT_FOUND_RESPONSE
)
async def get_task(task_id: TaskId, service: TaskServiceDependency, user: CurrentUser) -> TaskOut:
    return TaskOut.model_validate(await service.get(task_id, user.id))


@router.patch(
    "/{task_id}", response_model=TaskOut, summary="Update a task", responses=NOT_FOUND_RESPONSE
)
async def update_task(
    task_id: TaskId, data: TaskUpdate, service: TaskServiceDependency, user: CurrentUser
) -> TaskOut:
    return TaskOut.model_validate(await service.update(task_id, data, user.id))


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
    responses=NOT_FOUND_RESPONSE,
)
async def delete_task(
    task_id: TaskId, service: TaskServiceDependency, user: CurrentUser
) -> Response:
    await service.delete(task_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
