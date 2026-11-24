from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.v1.dependencies import WorkspaceServiceDep
from app.core.api_docs import error_responses
from app.core.database import Session
from app.core.dependencies import CurrentUser
from app.models.task import Task
from app.repositories.task import TaskRepository
from app.schemas.pagination import TaskPage
from app.schemas.task import StandaloneTaskQuery, TaskCreate, TaskOut, TaskUpdate
from app.services.task import TaskService

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def get_task_service(
    session: Session, request: Request, workspace: WorkspaceServiceDep
) -> TaskService:
    task_repository = TaskRepository(session)

    return TaskService(task_repository, workspace, request.app.state.task_cache)


def to_task_out(task: Task) -> TaskOut:
    return TaskOut.model_validate(task)


TaskServiceDependency = Annotated[
    TaskService,
    Depends(get_task_service),
]


@router.post(
    "",
    response_model=TaskOut,
    status_code=201,
    summary="Create a standalone task",
    description="Create a task owned by the signed-in account.",
    responses=error_responses(401, 422),
)
async def create(
    data: TaskCreate,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> TaskOut:
    task = await service.create(data, current_user)
    return to_task_out(task)


@router.get(
    "",
    response_model=TaskPage,
    summary="Search standalone tasks",
    description="Search title or description and combine filters with offset pagination. Members see their tasks and administrators see all standalone tasks.",
    responses=error_responses(401, 422),
)
async def page(
    service: TaskServiceDependency,
    current_user: CurrentUser,
    query: Annotated[StandaloneTaskQuery, Query()],
) -> TaskPage:
    return await service.page(query, current_user)


@router.get(
    "/{identifier}",
    response_model=TaskOut,
    summary="Read a task by ID",
    description="Return the requested task if it is visible to the signed-in account.",
    responses=error_responses(401, 404, 422),
)
async def read(
    identifier: int,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> TaskOut:
    return await service.get(identifier, current_user)


@router.patch(
    "/{identifier}",
    response_model=TaskOut,
    summary="Update a task by ID",
    description="Apply the provided fields. Changing completed also updates the task status.",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def update(
    identifier: int,
    data: TaskUpdate,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> TaskOut:
    task = await service.update(identifier, data, current_user)

    return to_task_out(task)


@router.delete(
    "/{identifier}",
    status_code=204,
    summary="Delete a task by ID",
    description="Delete an accessible task and return an empty response.",
    responses=error_responses(401, 403, 404, 409, 422),
)
async def delete(
    identifier: int,
    service: TaskServiceDependency,
    current_user: CurrentUser,
) -> Response:
    await service.delete(identifier, current_user)

    return Response(status_code=204)
