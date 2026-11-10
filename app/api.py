import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool

from app.database import Session
from app.models import Task
from app.repositories import BaseRepository, UserRepository
from app.schemas import Register, TaskCreate, TaskOut, TaskPage, TaskUpdate, Token, UserOut
from app.security import Admin, CurrentUser, issue_token, passwords
from app.services import TaskService

router = APIRouter(prefix="/api")


@router.post("/auth/register", response_model=UserOut, status_code=201, tags=["Authentication"])
async def register(data: Register, session: Session) -> object:
    hashed = await run_in_threadpool(passwords.hash, data.password)
    try:
        return await UserRepository(session).create(username=data.username, password_hash=hashed)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(409, "Username already exists") from None


@router.post("/auth/token", response_model=Token, tags=["Authentication"])
async def login(
    request: Request,
    session: Session,
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    user = await UserRepository(session).by_username(form.username)
    hashed = user.password_hash if user else request.app.state.dummy_hash
    valid = await run_in_threadpool(passwords.verify, form.password, hashed)
    if not valid or user is None:
        raise HTTPException(401, "Incorrect credentials", headers={"WWW-Authenticate": "Bearer"})
    settings = request.app.state.settings
    return Token(access_token=issue_token(user, settings.jwt_secret, settings.token_minutes))


@router.get("/users/me", response_model=UserOut, tags=["Users"])
async def me(user: CurrentUser) -> object:
    return user


@router.get("/admin/users", response_model=list[UserOut], tags=["Administration"])
async def users(
    session: Session,
    admin: Admin,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> object:
    rows, _ = await UserRepository(session).page(offset, limit)
    return rows


@router.post("/tasks", response_model=TaskOut, status_code=201, tags=["Tasks"])
async def create_task(data: TaskCreate, session: Session, user: CurrentUser) -> object:
    return await BaseRepository(session, Task).create(**data.model_dump(), owner_id=user.id)


@router.get("/tasks", response_model=TaskPage, tags=["Tasks"])
async def list_tasks(
    session: Session,
    user: CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> TaskPage:
    filters = () if user.role == "admin" else (Task.owner_id == user.id,)
    rows, total = await BaseRepository(session, Task).page(offset, limit, *filters)
    return TaskPage(
        items=[TaskOut.model_validate(row) for row in rows], total=total, offset=offset, limit=limit
    )


@router.get("/tasks/{identifier}", response_model=TaskOut, tags=["Tasks"])
async def read_task(
    identifier: int,
    request: Request,
    session: Session,
    user: CurrentUser,
) -> TaskOut:
    # Always authorize against DB before consulting cached content.
    task = await TaskService(session).owned(identifier, user)
    key = f"tasks:{task.id}:{task.owner_id}:{task.title}:{task.description}:{task.completed}"
    key = "task:" + hashlib.sha256(key.encode()).hexdigest()
    cached = await request.app.state.cache.get(key)
    if cached:
        return TaskOut.model_validate_json(cached)
    result = TaskOut.model_validate(task)
    await request.app.state.cache.put(key, result.model_dump_json())
    return result


@router.patch("/tasks/{identifier}", response_model=TaskOut, tags=["Tasks"])
async def update_task(
    identifier: int,
    data: TaskUpdate,
    session: Session,
    user: CurrentUser,
) -> object:
    service = TaskService(session)
    task = await service.owned(identifier, user)
    return await service.repository.update(task, data.model_dump(exclude_unset=True))


@router.delete("/tasks/{identifier}", status_code=204, tags=["Tasks"])
async def delete_task(identifier: int, session: Session, user: CurrentUser) -> Response:
    service = TaskService(session)
    await service.repository.delete(await service.owned(identifier, user))
    return Response(status_code=204)
