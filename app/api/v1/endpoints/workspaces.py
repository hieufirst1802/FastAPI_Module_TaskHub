from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.v1.dependencies import WorkspaceServiceDep
from app.core.api_docs import error_responses
from app.core.constants import API_V1_PREFIX
from app.core.dependencies import CurrentUser
from app.schemas.auth import ProfileUpdate, UserResponse
from app.schemas.pagination import Page, PaginationDep
from app.schemas.task import ProjectTaskFilters
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

router = APIRouter(prefix=API_V1_PREFIX)


@router.get(
    "/users/me",
    response_model=UserResponse,
    summary="Read my profile",
    description="Return the signed-in account profile.",
    responses=error_responses(401),
    tags=["Users"],
)
async def profile(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)


@router.patch(
    "/users/me",
    response_model=UserResponse,
    summary="Update my profile",
    description="Update the full name or email on the signed-in account.",
    responses=error_responses(401, 409, 422),
    tags=["Users"],
)
async def update_profile(
    data: ProfileUpdate, user: CurrentUser, service: WorkspaceServiceDep
) -> UserResponse:
    return UserResponse.model_validate(await service.update_profile(user, data))


@router.post(
    "/workspaces",
    response_model=WorkspaceOut,
    status_code=201,
    summary="Create a workspace",
    description="Create a workspace and make the signed-in account its owner.",
    responses=error_responses(401, 422),
    tags=["Workspaces"],
)
async def create_workspace(
    data: Named, service: WorkspaceServiceDep, user: CurrentUser
) -> WorkspaceOut:
    return WorkspaceOut.model_validate(await service.create_workspace(data.name, user))


@router.get(
    "/workspaces",
    response_model=Page[WorkspaceOut],
    summary="List visible workspaces",
    description="Return a page of workspaces visible to the signed-in account.",
    responses=error_responses(401, 422),
    tags=["Workspaces"],
)
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


@router.get(
    "/workspaces/{wid}",
    response_model=WorkspaceOut,
    summary="Read a workspace",
    description="Return a workspace visible to the signed-in account.",
    responses=error_responses(401, 404, 422),
    tags=["Workspaces"],
)
async def read_workspace(wid: int, service: WorkspaceServiceDep, user: CurrentUser) -> WorkspaceOut:
    return WorkspaceOut.model_validate(await service.authorize(wid, user))


@router.patch(
    "/workspaces/{wid}",
    response_model=WorkspaceOut,
    summary="Rename a workspace",
    description="Change the workspace name with owner or administrator access.",
    responses=error_responses(401, 403, 404, 422),
    tags=["Workspaces"],
)
async def update_workspace(
    wid: int, data: Named, service: WorkspaceServiceDep, user: CurrentUser
) -> WorkspaceOut:
    workspace = await service.authorize(wid, user, owner=True)
    return WorkspaceOut.model_validate(
        await service.workspaces.update(workspace, {"name": data.name})
    )


@router.delete(
    "/workspaces/{wid}",
    status_code=204,
    summary="Delete a workspace",
    description="Delete the workspace and its associated projects and tasks.",
    responses=error_responses(401, 403, 404, 422),
    tags=["Workspaces"],
)
async def delete_workspace(wid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_workspace(wid, user)
    return Response(status_code=204)


@router.get(
    "/workspaces/{wid}/members",
    response_model=list[MemberOut],
    summary="List workspace members",
    description="Return workspace members and their roles.",
    responses=error_responses(401, 404, 422),
    tags=["Workspaces"],
)
async def members(wid: int, service: WorkspaceServiceDep, user: CurrentUser) -> list[MemberOut]:
    return [MemberOut.model_validate(m) for m in await service.member_list(wid, user)]


@router.post(
    "/workspaces/{wid}/members",
    response_model=MemberOut,
    status_code=201,
    summary="Add a workspace member",
    description="Grant EDITOR or VIEWER access to an existing active account.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Workspaces"],
)
async def invite_member(
    wid: int, data: MemberInput, service: WorkspaceServiceDep, user: CurrentUser
) -> MemberOut:
    return MemberOut.model_validate(await service.set_member(wid, data.user_id, data.role, user))


@router.patch(
    "/workspaces/{wid}/members/{uid}",
    response_model=MemberOut,
    summary="Change a workspace role",
    description="Set an existing member's role to EDITOR or VIEWER.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Workspaces"],
)
async def change_role(
    wid: int, uid: int, data: MemberUpdate, service: WorkspaceServiceDep, user: CurrentUser
) -> MemberOut:
    return MemberOut.model_validate(
        await service.set_member(wid, uid, data.role, user, require_existing=True)
    )


@router.delete(
    "/workspaces/{wid}/members/{uid}",
    status_code=204,
    summary="Remove a workspace member",
    description="Remove membership and clear that account's task assignments in the workspace.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Workspaces"],
)
async def remove_member(
    wid: int, uid: int, service: WorkspaceServiceDep, user: CurrentUser
) -> Response:
    await service.remove_member(wid, uid, user)
    return Response(status_code=204)


@router.post(
    "/workspaces/{wid}/projects",
    response_model=ProjectOut,
    status_code=201,
    summary="Create a project",
    description="Create a project in a workspace with write access.",
    responses=error_responses(401, 403, 404, 422),
    tags=["Projects"],
)
async def create_project(
    wid: int, data: ProjectInput, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectOut:
    return ProjectOut.model_validate(await service.create_project(wid, data, user))


@router.get(
    "/workspaces/{wid}/projects",
    response_model=Page[ProjectOut],
    summary="List workspace projects",
    description="Return a page of projects belonging to an accessible workspace.",
    responses=error_responses(401, 404, 422),
    tags=["Projects"],
)
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


@router.get(
    "/projects/{pid}",
    response_model=ProjectOut,
    summary="Read a project",
    description="Return project details for an accessible project.",
    responses=error_responses(401, 404, 422),
    tags=["Projects"],
)
async def read_project(pid: int, service: WorkspaceServiceDep, user: CurrentUser) -> ProjectOut:
    return ProjectOut.model_validate(await service.project(pid, user))


@router.patch(
    "/projects/{pid}",
    response_model=ProjectOut,
    summary="Update a project",
    description="Rename a project or change its archive status.",
    responses=error_responses(401, 403, 404, 422),
    tags=["Projects"],
)
async def update_project(
    pid: int, data: ProjectUpdate, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectOut:
    return ProjectOut.model_validate(await service.update_project(pid, data, user))


@router.delete(
    "/projects/{pid}",
    status_code=204,
    summary="Delete a project",
    description="Delete the project and its associated tasks, labels, and comments.",
    responses=error_responses(401, 403, 404, 422),
    tags=["Projects"],
)
async def delete_project(pid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_project(pid, user)
    return Response(status_code=204)


@router.post(
    "/projects/{pid}/tasks",
    response_model=ProjectTaskOut,
    status_code=201,
    summary="Create a project task",
    description="Create a task in an active project. The optional assignee must be an active workspace member.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Project Tasks"],
)
async def create_task(
    pid: int, data: ProjectTaskCreate, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.create_task(pid, data, user))


@router.get(
    "/projects/{pid}/tasks",
    response_model=Page[ProjectTaskOut],
    summary="Search project tasks",
    description="Search title or description and combine status, priority, and assignee filters with page-based pagination.",
    responses=error_responses(401, 404, 422),
    tags=["Project Tasks"],
)
async def tasks(
    pid: int,
    service: WorkspaceServiceDep,
    user: CurrentUser,
    query: Annotated[ProjectTaskFilters, Query()],
) -> Page[ProjectTaskOut]:
    return await service.task_page(pid, user, query)


@router.get(
    "/tasks/{tid}",
    response_model=ProjectTaskOut,
    summary="Read a project task",
    description="Return task details after checking workspace access.",
    responses=error_responses(401, 404, 422),
    tags=["Project Tasks"],
)
async def read_task(tid: int, service: WorkspaceServiceDep, user: CurrentUser) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.task(tid, user))


@router.patch(
    "/tasks/{tid}",
    response_model=ProjectTaskOut,
    summary="Update a project task",
    description="Apply the supplied fields. Send null to clear the assignee or due date.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Project Tasks"],
)
async def update_task(
    tid: int, data: ProjectTaskUpdate, service: WorkspaceServiceDep, user: CurrentUser
) -> ProjectTaskOut:
    return ProjectTaskOut.model_validate(await service.update_task(tid, data, user))


@router.delete(
    "/tasks/{tid}",
    status_code=204,
    summary="Delete a project task",
    description="Delete the task and its associated comments and label links.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Project Tasks"],
)
async def delete_task(tid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_task(tid, user)
    return Response(status_code=204)


@router.post(
    "/projects/{pid}/labels",
    response_model=LabelOut,
    status_code=201,
    summary="Create a project label",
    description="Create a label with a name unique within the project.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Labels"],
)
async def create_label(
    pid: int, data: LabelInput, service: WorkspaceServiceDep, user: CurrentUser
) -> LabelOut:
    return LabelOut.model_validate(await service.create_label(pid, data, user))


@router.get(
    "/projects/{pid}/labels",
    response_model=list[LabelOut],
    summary="List project labels",
    description="Return the labels defined for the project.",
    responses=error_responses(401, 404, 422),
    tags=["Labels"],
)
async def labels(pid: int, service: WorkspaceServiceDep, user: CurrentUser) -> list[LabelOut]:
    return [LabelOut.model_validate(label) for label in await service.label_list(pid, user)]


@router.patch(
    "/labels/{lid}",
    response_model=LabelOut,
    summary="Update a label",
    description="Set the label name and color. Omitting the color uses the default gray.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Labels"],
)
async def update_label(
    lid: int, data: LabelInput, service: WorkspaceServiceDep, user: CurrentUser
) -> LabelOut:
    return LabelOut.model_validate(await service.update_label(lid, data, user))


@router.delete(
    "/labels/{lid}",
    status_code=204,
    summary="Delete a label",
    description="Remove the label and its task links.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Labels"],
)
async def delete_label(lid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_label(lid, user)
    return Response(status_code=204)


@router.get(
    "/tasks/{tid}/labels",
    response_model=list[LabelOut],
    summary="List task labels",
    description="Return the labels attached to the task.",
    responses=error_responses(401, 404, 422),
    tags=["Labels"],
)
async def task_labels(tid: int, service: WorkspaceServiceDep, user: CurrentUser) -> list[LabelOut]:
    return [LabelOut.model_validate(label) for label in await service.task_label_list(tid, user)]


@router.post(
    "/tasks/{tid}/labels/{lid}",
    status_code=204,
    summary="Attach a label",
    description="Link a label to a task in the same project.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Labels"],
)
async def attach_label(
    tid: int, lid: int, service: WorkspaceServiceDep, user: CurrentUser
) -> Response:
    await service.attach_label(tid, lid, user)
    return Response(status_code=204)


@router.delete(
    "/tasks/{tid}/labels/{lid}",
    status_code=204,
    summary="Detach a label",
    description="Remove a task's link to a label in the same project.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Labels"],
)
async def detach_label(
    tid: int, lid: int, service: WorkspaceServiceDep, user: CurrentUser
) -> Response:
    await service.attach_label(tid, lid, user, remove=True)
    return Response(status_code=204)


@router.post(
    "/tasks/{tid}/comments",
    response_model=CommentOut,
    status_code=201,
    summary="Add a comment",
    description="Post a comment on a task in an active project.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Comments"],
)
async def add_comment(
    tid: int, data: CommentInput, service: WorkspaceServiceDep, user: CurrentUser
) -> CommentOut:
    return CommentOut.model_validate(await service.add_comment(tid, data.content, user))


@router.get(
    "/tasks/{tid}/comments",
    response_model=Page[CommentOut],
    summary="List task comments",
    description="Return a page of comments on an accessible task.",
    responses=error_responses(401, 404, 422),
    tags=["Comments"],
)
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


@router.delete(
    "/comments/{cid}",
    status_code=204,
    summary="Delete a comment",
    description="Remove a comment if the account has permission to delete it.",
    responses=error_responses(401, 403, 404, 409, 422),
    tags=["Comments"],
)
async def delete_comment(cid: int, service: WorkspaceServiceDep, user: CurrentUser) -> Response:
    await service.delete_comment(cid, user)
    return Response(status_code=204)
