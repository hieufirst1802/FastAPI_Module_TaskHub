from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.repositories import TaskRepository
from app.schemas import TaskCreate, TaskOut, TaskUpdate
from app.services import TaskService

router = APIRouter(prefix="/api", tags=["Tasks"])


def get_repository(request: Request) -> TaskRepository:
    repository: TaskRepository = request.app.state.repository
    return repository


Repository = Annotated[TaskRepository, Depends(get_repository)]


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create(data: TaskCreate, repository: Repository) -> TaskOut:
    return repository.create(data)


@router.get("/tasks", response_model=list[TaskOut])
def page(
    repository: Repository, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
) -> list[TaskOut]:
    return repository.page(offset, limit)


@router.get("/tasks/{identifier}", response_model=TaskOut)
def read(identifier: int, repository: Repository) -> TaskOut:
    return TaskService(repository).get(identifier)


@router.patch("/tasks/{identifier}", response_model=TaskOut)
def update(identifier: int, data: TaskUpdate, repository: Repository) -> TaskOut:
    return TaskService(repository).update(identifier, data)


@router.delete("/tasks/{identifier}", status_code=204)
def delete(identifier: int, repository: Repository) -> Response:
    TaskService(repository).delete(identifier)
    return Response(status_code=204)
