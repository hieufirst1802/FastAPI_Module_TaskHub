from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.database import Session
from app.core.dependencies import CurrentUser
from app.schemas.auth import ProfileUpdate, UserResponse
from app.schemas.workspace import (
    CommentInput,
    CommentOut,
    LabelInput,
    LabelOut,
    MemberInput,
    MemberOut,
    MemberUpdate,
    Named,
    Priority,
    ProjectInput,
    ProjectOut,
    ProjectTaskCreate,
    ProjectTaskOut,
    ProjectTaskPage,
    ProjectTaskUpdate,
    ProjectUpdate,
    TaskStatus,
    WorkspaceOut,
)
from app.services.workspace import WorkspaceService

router = APIRouter(prefix="/api/v1", tags=["Workspaces & Projects"])


def get_service(session: Session, request: Request) -> WorkspaceService:
    return WorkspaceService(session, request.app.state.task_cache)


Service = Annotated[WorkspaceService, Depends(get_service)]


@router.get("/users/me", response_model=UserResponse)
async def profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch("/users/me", response_model=UserResponse)
async def update_profile(data: ProfileUpdate, user: CurrentUser, service: Service) -> UserResponse:
    return UserResponse.model_validate(await service.update_profile(user, data))


@router.post("/workspaces", response_model=WorkspaceOut, status_code=201)
async def create_workspace(data: Named, service: Service, user: CurrentUser) -> WorkspaceOut:
    return WorkspaceOut.model_validate(await service.create_workspace(data.name, user))


@router.get("/workspaces", response_model=list[WorkspaceOut])
async def list_workspaces(
    service: Service,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[WorkspaceOut]:
    rows, _ = await service.workspace_page(user, (page - 1) * limit, limit)
    return [WorkspaceOut.model_validate(w) for w in rows]


@router.get("/workspaces/{wid}", response_model=WorkspaceOut)
async def read_workspace(wid: int, service: Service, user: CurrentUser) -> WorkspaceOut:
    return WorkspaceOut.model_validate(await service.authorize(wid, user))


@router.patch("/workspaces/{wid}", response_model=WorkspaceOut)
async def update_workspace(
    wid: int, data: Named, service: Service, user: CurrentUser
) -> WorkspaceOut:
    workspace = await service.authorize(wid, user, owner=True)
    return WorkspaceOut.model_validate(
        await service.workspaces.update(workspace, {"name": data.name})
    )


@router.delete("/workspaces/{wid}", status_code=204)
async def delete_workspace(wid: int, service: Service, user: CurrentUser) -> Response:
    await service.delete_workspace(wid, user)
    return Response(status_code=204)


@router.get("/workspaces/{wid}/members", response_model=list[MemberOut])
async def members(wid: int, service: Service, user: CurrentUser) -> list[MemberOut]:
    return [MemberOut.model_validate(m) for m in await service.member_list(wid, user)]


@router.post("/workspaces/{wid}/members", response_model=MemberOut, status_code=201)
async def invite_member(
    wid: int, data: MemberInput, service: Service, user: CurrentUser
) -> MemberOut:
    return MemberOut.model_validate(await service.set_member(wid, data.user_id, data.role, user))


@router.patch("/workspaces/{wid}/members/{uid}", response_model=MemberOut)
async def change_role(
    wid: int, uid: int, data: MemberUpdate, service: Service, user: CurrentUser
) -> MemberOut:
    return MemberOut.model_validate(
        await service.set_member(wid, uid, data.role, user, require_existing=True)
    )


@router.delete("/workspaces/{wid}/members/{uid}", status_code=204)
async def remove_member(wid: int, uid: int, service: Service, user: CurrentUser) -> Response:
    await service.remove_member(wid, uid, user)
    return Response(status_code=204)


@router.post("/workspaces/{wid}/projects", response_model=ProjectOut, status_code=201)
async def create_project(
    wid: int, data: ProjectInput, service: Service, user: CurrentUser
) -> ProjectOut:
    return ProjectOut.model_validate(await service.create_project(wid, data, user))


@router.get("/workspaces/{wid}/projects", response_model=list[ProjectOut])
async def projects(
    wid: int,
    service: Service,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[ProjectOut]:
    return [
        ProjectOut.model_validate(p) for p in await service.project_page(wid, user, page, limit)
    ]


@router.get("/projects/{pid}", response_model=ProjectOut)
async def read_project(pid: int, service: Service, user: CurrentUser) -> ProjectOut:
    return ProjectOut.model_validate(await service.project(pid, user))


@router.patch("/projects/{pid}", response_model=ProjectOut)
async def update_project(
    pid: int, data: ProjectUpdate, service: Service, user: CurrentUser
) -> ProjectOut:
    return ProjectOut.model_validate(await service.update_project(pid, data, user))


@router.delete("/projects/{pid}", status_code=204)
async def delete_project(pid: int, service: Service, user: CurrentUser) -> Response:
    await service.delete_project(pid, user)
    return Response(status_code=204)


@router.post("/projects/{pid}/tasks", response_model=ProjectTaskOut, status_code=201)
async def create_task(
    pid: int, data: ProjectTaskCreate, service: Service, user: CurrentUser
) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.create_task(pid, data, user))


@router.get("/projects/{pid}/tasks", response_model=ProjectTaskPage)
async def tasks(
    pid: int,
    service: Service,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    status: TaskStatus | None = None,
    priority: Priority | None = None,
    assignee_id: int | None = Query(None, gt=0),
) -> ProjectTaskPage:
    return await service.task_page(pid, user, page, limit, status, priority, assignee_id)


@router.get("/tasks/{tid}", response_model=ProjectTaskOut)
async def read_task(tid: int, service: Service, user: CurrentUser) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.task(tid, user))


@router.patch("/tasks/{tid}", response_model=ProjectTaskOut)
async def update_task(
    tid: int, data: ProjectTaskUpdate, service: Service, user: CurrentUser
) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.update_task(tid, data, user))


@router.delete("/tasks/{tid}", status_code=204)
async def delete_task(tid: int, service: Service, user: CurrentUser) -> Response:
    await service.delete_task(tid, user)
    return Response(status_code=204)


@router.post("/projects/{pid}/labels", response_model=LabelOut, status_code=201)
async def create_label(pid: int, data: LabelInput, service: Service, user: CurrentUser) -> LabelOut:
    return LabelOut.model_validate(await service.create_label(pid, data, user))


@router.get("/projects/{pid}/labels", response_model=list[LabelOut])
async def labels(pid: int, service: Service, user: CurrentUser) -> list[LabelOut]:
    return [LabelOut.model_validate(label) for label in await service.label_list(pid, user)]


@router.patch("/labels/{lid}", response_model=LabelOut)
async def update_label(lid: int, data: LabelInput, service: Service, user: CurrentUser) -> LabelOut:
    return LabelOut.model_validate(await service.update_label(lid, data, user))


@router.delete("/labels/{lid}", status_code=204)
async def delete_label(lid: int, service: Service, user: CurrentUser) -> Response:
    await service.delete_label(lid, user)
    return Response(status_code=204)


@router.get("/tasks/{tid}/labels", response_model=list[LabelOut])
async def task_labels(tid: int, service: Service, user: CurrentUser) -> list[LabelOut]:
    return [LabelOut.model_validate(label) for label in await service.task_label_list(tid, user)]


@router.post("/tasks/{tid}/labels/{lid}", status_code=204)
async def attach_label(tid: int, lid: int, service: Service, user: CurrentUser) -> Response:
    await service.attach_label(tid, lid, user)
    return Response(status_code=204)


@router.delete("/tasks/{tid}/labels/{lid}", status_code=204)
async def detach_label(tid: int, lid: int, service: Service, user: CurrentUser) -> Response:
    await service.attach_label(tid, lid, user, remove=True)
    return Response(status_code=204)


@router.post("/tasks/{tid}/comments", response_model=CommentOut, status_code=201)
async def add_comment(
    tid: int, data: CommentInput, service: Service, user: CurrentUser
) -> CommentOut:
    return CommentOut.model_validate(await service.add_comment(tid, data.content, user))


@router.get("/tasks/{tid}/comments", response_model=list[CommentOut])
async def comments(
    tid: int,
    service: Service,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[CommentOut]:
    return [
        CommentOut.model_validate(c) for c in await service.comment_page(tid, user, page, limit)
    ]


@router.delete("/comments/{cid}", status_code=204)
async def delete_comment(cid: int, service: Service, user: CurrentUser) -> Response:
    await service.delete_comment(cid, user)
    return Response(status_code=204)
