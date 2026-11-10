from fastapi import APIRouter, HTTPException, Query, Response

from app.database import Session
from app.models import Task
from app.repositories import BaseRepository, UserRepository
from app.schemas import TaskCreate, TaskOut, TaskPage, TaskUpdate

router = APIRouter(prefix="/api", tags=["Tasks"])


async def find_task(identifier: int, session: Session) -> Task:
    task = await BaseRepository(session, Task).get(identifier)
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.post("/tasks", response_model=TaskOut, status_code=201)
async def create(data: TaskCreate, session: Session) -> object:
    # Fixed demo user illustrates the relationship before authentication in lesson 3.
    users = UserRepository(session)
    owner = await users.by_username("demo")
    if owner is None:
        owner = await users.create(username="demo", password_hash="disabled-login")
    return await BaseRepository(session, Task).create(**data.model_dump(), owner_id=owner.id)


@router.get("/tasks", response_model=TaskPage)
async def page(
    session: Session, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)
) -> TaskPage:
    rows, total = await BaseRepository(session, Task).page(offset, limit)
    return TaskPage(
        items=[TaskOut.model_validate(row) for row in rows], total=total, offset=offset, limit=limit
    )


@router.get("/tasks/{identifier}", response_model=TaskOut)
async def read(identifier: int, session: Session) -> object:
    return await find_task(identifier, session)


@router.patch("/tasks/{identifier}", response_model=TaskOut)
async def update(identifier: int, data: TaskUpdate, session: Session) -> object:
    task = await find_task(identifier, session)
    return await BaseRepository(session, Task).update(task, data.model_dump(exclude_unset=True))


@router.delete("/tasks/{identifier}", status_code=204)
async def delete(identifier: int, session: Session) -> Response:
    await BaseRepository(session, Task).delete(await find_task(identifier, session))
    return Response(status_code=204)
