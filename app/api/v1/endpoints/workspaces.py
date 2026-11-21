from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.v1.dependencies import WorkspaceServiceDep
from app.core.constants import API_V1_PREFIX
from app.core.dependencies import CurrentUser
from app.enums import Priority, TaskStatus
from app.schemas.auth import ProfileUpdate, UserResponse
from app.schemas.pagination import Page, PaginationDep
from app.schemas.workspace import (
    CommentInput,
    CommentOut,
    LabelInput,
    LabelOut,
    MemberInput,
    MemberOut,
    MemberUpdate,
    Named,
    ProjectInput,
    ProjectOut,
    ProjectTaskCreate,
    ProjectTaskOut,
    ProjectTaskUpdate,
    ProjectUpdate,
    WorkspaceOut,
)

router = APIRouter(prefix=API_V1_PREFIX, tags=["Workspaces & Projects"])


@router.get("/users/me", response_model=UserResponse)
async def profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/users/me", response_model=UserResponse)
async def update_profile(
    data: ProfileUpdate, user: CurrentUser, service: WorkspaceServiceDep
) -> UserResponse:
    return UserResponse.model_validate(await service.update_profile(user, data))


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    data: Named, service: WorkspaceServiceDep, user: CurrentUser
) -> WorkspaceOut:
    return WorkspaceOut.model_validate(await service.create_workspace(data.name, user))


@router.get("/workspaces", response_model=Page[WorkspaceOut])
async def list_workspaces(
    service: WorkspaceServiceDep,
    user: CurrentUser,
    pagination: PaginationDep,
) -> Page[WorkspaceOut]:
    rows, total = await service.workspace_page(user, pagination)
    return Page[WorkspaceOut](
        items=[WorkspaceOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.get("/workspaces/{wid}", response_model=WorkspaceOut)
async def read_workspace(wid: int, service: WorkspaceServiceDep, user: CurrentUser) -> WorkspaceOut:
    return WorkspaceOut.model_validate(await service.authorize(wid, user))


@router.patch("/workspaces/{wid}", response_model=WorkspaceOut)
async def update_workspace(
    wid: int, data: Named, service: WorkspaceServiceDep, user: CurrentUser
) -> WorkspaceOut:
    workspace = await service.authorize(wid, user, owner=True)
    return WorkspaceOut.model_validate(
        await service.workspaces.update(workspace, {"name": data.name})
    )


@router.delete("/workspaces/{wid}", status_code=204)
async def delete_workspace(wid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_workspace(wid, user)
    return Response(status_code=204)


@router.get("/workspaces/{wid}/members", response_model=list[MemberOut])
async def members(wid: int, service: WorkspaceServiceDep, user: CurrentUser) -> list[MemberOut]:
    return [MemberOut.model_validate(m) for m in await service.member_list(wid, user)]


@router.post("/workspaces/{wid}/members", response_model=MemberOut, status_code=201)
async def invite_member(
    wid: int, data: MemberInput, service: WorkspaceServiceDep, user: CurrentUser
) -> MemberOut:
    return MemberOut.model_validate(await service.set_member(wid, data.user_id, data.role, user))


@router.patch("/workspaces/{wid}/members/{uid}", response_model=MemberOut)
async def change_role(
    wid: int, uid: int, data: MemberUpdate, service: WorkspaceServiceDep, user: CurrentUser
) -> MemberOut:
    return MemberOut.model_validate(
        await service.set_member(wid, uid, data.role, user, require_existing=True)
    )


@router.delete("/workspaces/{wid}/members/{uid}", status_code=204)
async def remove_member(
    wid: int, uid: int, service: WorkspaceServiceDep, user: CurrentUser
) -> Response:
    await service.remove_member(wid, uid, user)
    return Response(status_code=204)


@router.post("/workspaces/{wid}/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    wid: int, data: ProjectInput, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectOut:
    return ProjectOut.model_validate(await service.create_project(wid, data, user))


@router.get("/workspaces/{wid}/projects", response_model=Page[ProjectOut])
async def projects(
    wid: int,
    service: WorkspaceServiceDep,
    user: CurrentUser,
    pagination: PaginationDep,
) -> Page[ProjectOut]:
    rows, total = await service.project_page(wid, user, pagination)
    return Page[ProjectOut](
        items=[ProjectOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.get("/projects/{pid}", response_model=ProjectOut)
async def read_project(pid: int, service: WorkspaceServiceDep, user: CurrentUser) -> ProjectOut:
    return ProjectOut.model_validate(await service.project(pid, user))


@router.patch("/projects/{pid}", response_model=ProjectOut)
async def update_project(
    pid: int, data: ProjectUpdate, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectOut:
    return ProjectOut.model_validate(await service.update_project(pid, data, user))


@router.delete("/projects/{pid}", status_code=204)
async def delete_project(pid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_project(pid, user)
    return Response(status_code=204)


@router.post("/projects/{pid}/tasks", response_model=ProjectTaskOut, status_code=201)
async def create_task(
    pid: int, data: ProjectTaskCreate, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.create_task(pid, data, user))


@router.get("/projects/{pid}/tasks", response_model=Page[ProjectTaskOut])
async def tasks(
    pid: int,
    service: WorkspaceServiceDep,
    user: CurrentUser,
    pagination: PaginationDep,
    status: TaskStatus | None = None,
    priority: Priority | None = None,
    assignee_id: Annotated[int | None, Query(gt=0)] = None,
) -> Page[ProjectTaskOut]:
    return await service.task_page(pid, user, pagination, status, priority, assignee_id)


@router.get("/tasks/{tid}", response_model=ProjectTaskOut)
async def read_task(tid: int, service: WorkspaceServiceDep, user: CurrentUser) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.task(tid, user))


@router.patch("/tasks/{tid}", response_model=ProjectTaskOut)
async def update_task(
    tid: int, data: ProjectTaskUpdate, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.update_task(tid, data, user))


@router.delete("/tasks/{tid}", status_code=204)
async def delete_task(tid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_task(tid, user)
    return Response(status_code=204)


@router.post("/projects/{pid}/labels", response_model=LabelOut, status_code=201)
async def create_label(
    pid: int, data: LabelInput, service: WorkspaceServiceDep, user: CurrentUser
) -> LabelOut:
    return LabelOut.model_validate(await service.create_label(pid, data, user))


@router.get("/projects/{pid}/labels", response_model=list[LabelOut])
async def labels(pid: int, service: WorkspaceServiceDep, user: CurrentUser) -> list[LabelOut]:
    return [LabelOut.model_validate(label) for label in await service.label_list(pid, user)]


@router.patch("/labels/{lid}", response_model=LabelOut)
async def update_label(
    lid: int, data: LabelInput, service: WorkspaceServiceDep, user: CurrentUser
) -> LabelOut:
    return LabelOut.model_validate(await service.update_label(lid, data, user))


@router.delete("/labels/{lid}", status_code=204)
async def delete_label(lid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_label(lid, user)
    return Response(status_code=204)


@router.get("/tasks/{tid}/labels", response_model=list[LabelOut])
async def task_labels(tid: int, service: WorkspaceServiceDep, user: CurrentUser) -> list[LabelOut]:
    return [LabelOut.model_validate(label) for label in await service.task_label_list(tid, user)]


@router.post("/tasks/{tid}/labels/{lid}", status_code=204)
async def attach_label(
    tid: int, lid: int, service: WorkspaceServiceDep, user: CurrentUser
) -> Response:
    await service.attach_label(tid, lid, user)
    return Response(status_code=204)


@router.delete("/tasks/{tid}/labels/{lid}", status_code=204)
async def detach_label(
    tid: int, lid: int, service: WorkspaceServiceDep, user: CurrentUser
) -> Response:
    await service.attach_label(tid, lid, user, remove=True)
    return Response(status_code=204)


@router.post("/tasks/{tid}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    tid: int, data: CommentInput, service: WorkspaceServiceDep, user: CurrentUser
) -> CommentOut:
    return CommentOut.model_validate(await service.add_comment(tid, data.content, user))


@router.get("/tasks/{tid}/comments", response_model=Page[CommentOut])
async def comments(
    tid: int,
    service: WorkspaceServiceDep,
    user: CurrentUser,
    pagination: PaginationDep,
) -> Page[CommentOut]:
    rows, total = await service.comment_page(tid, user, pagination)
    return Page[CommentOut](
        items=[CommentOut.model_validate(row) for row in rows],
        total=total,
        page=pagination.page,
        limit=pagination.limit,
    )


@router.delete("/comments/{cid}", status_code=204)
async def delete_comment(cid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_comment(cid, user)
    return Response(status_code=204)
