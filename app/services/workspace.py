from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import TaskCache
from app.core.exceptions import (
    ConflictException,
    EmailAlreadyExistsError,
    ForbiddenException,
    InvalidInputException,
    NotFoundException,
)
from app.core.integrity import LABEL_NAME_CONSTRAINT, USERS_EMAIL_CONSTRAINT, is_unique_violation
from app.core.messages import (
    ACTIVE_USER_NOT_FOUND,
    CANNOT_REMOVE_OWNER,
    COMMENT_NOT_FOUND,
    INSUFFICIENT_WORKSPACE_ROLE,
    INVALID_ASSIGNEE,
    LABEL_ALREADY_EXISTS,
    LABEL_NOT_FOUND,
    LABEL_PROJECT_MISMATCH,
    MEMBER_NOT_FOUND,
    OWNER_ROLE_IMMUTABLE,
    PROJECT_ARCHIVED,
    PROJECT_NOT_FOUND,
    PROJECT_TASK_NOT_FOUND,
    WORKSPACE_NOT_FOUND,
)
from app.enums import ProjectStatus, TaskStatus, UserRole, WorkspaceRole
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Comment, Label, Project, TaskLabel, Workspace, WorkspaceMember
from app.repositories.task import task_search_filters
from app.repositories.workspace import DomainRepository, MembershipRepository
from app.schemas.auth import ProfileUpdate
from app.schemas.pagination import Page, PaginationParams
from app.schemas.task import ProjectTaskFilters
from app.schemas.workspace import (
    LabelInput,
    ProjectInput,
    ProjectTaskCreate,
    ProjectTaskOut,
    ProjectTaskUpdate,
    ProjectUpdate,
)


class WorkspaceService:
    def __init__(self, session: AsyncSession, cache: TaskCache | None = None) -> None:
        self.session = session
        self.cache = cache
        self.members = MembershipRepository(session)
        self.workspaces = DomainRepository(session, Workspace)
        self.projects = DomainRepository(session, Project)
        self.tasks = DomainRepository(session, Task)
        self.labels = DomainRepository(session, Label)
        self.comments = DomainRepository(session, Comment)

    @asynccontextmanager
    async def _label_write(self) -> AsyncIterator[None]:
        try:
            yield
        except IntegrityError as exc:
            await self.session.rollback()
            if is_unique_violation(exc, LABEL_NAME_CONSTRAINT, "labels.project_id, labels.name"):
                raise ConflictException(LABEL_ALREADY_EXISTS) from exc
            raise

    async def authorize(
        self, workspace_id: int, user: User, write: bool = False, owner: bool = False
    ) -> Workspace:
        workspace = await self.workspaces.get(workspace_id)
        if workspace is None:
            raise NotFoundException(WORKSPACE_NOT_FOUND)
        if user.role == UserRole.ADMIN:
            return workspace
        member = await self.members.get(workspace_id, user.id)
        if member is None:
            raise NotFoundException(WORKSPACE_NOT_FOUND)
        if (owner and member.role != WorkspaceRole.OWNER) or (
            write and member.role == WorkspaceRole.VIEWER
        ):
            raise ForbiddenException(INSUFFICIENT_WORKSPACE_ROLE)
        return workspace

    async def workspace_page(
        self, user: User, pagination: PaginationParams
    ) -> tuple[list[Workspace], int]:
        if user.role == UserRole.ADMIN:
            return await self.workspaces.page(pagination.offset, pagination.limit)
        ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
        return await self.workspaces.page(
            pagination.offset, pagination.limit, Workspace.id.in_(ids)
        )

    async def create_workspace(self, name: str, user: User) -> Workspace:
        workspace = Workspace(name=name, owner_id=user.id)
        self.session.add(workspace)
        await self.session.flush()
        self.session.add(
            WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=WorkspaceRole.OWNER)
        )
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def set_member(
        self, wid: int, uid: int, role: WorkspaceRole, user: User, require_existing: bool = False
    ) -> WorkspaceMember:
        workspace = await self.authorize(wid, user, owner=True)
        if uid == workspace.owner_id:
            raise ConflictException(OWNER_ROLE_IMMUTABLE)
        target = await self.session.get(User, uid)
        if target is None or not target.is_active:
            raise NotFoundException(ACTIVE_USER_NOT_FOUND)
        member = await self.members.get(wid, uid)
        if require_existing and member is None:
            raise NotFoundException(MEMBER_NOT_FOUND)
        if member is None:
            member = WorkspaceMember(workspace_id=wid, user_id=uid, role=role)
            self.session.add(member)
        else:
            member.role = role
        await self.session.commit()
        return member

    async def remove_member(self, wid: int, uid: int, user: User) -> None:
        workspace = await self.authorize(wid, user, owner=True)
        if uid == workspace.owner_id:
            raise ConflictException(CANNOT_REMOVE_OWNER)
        member = await self.members.get(wid, uid)
        if member is None:
            raise NotFoundException(MEMBER_NOT_FOUND)
        project_ids = select(Project.id).where(Project.workspace_id == wid)
        task_ids = list(
            await self.session.scalars(
                select(Task.id).where(Task.project_id.in_(project_ids), Task.assignee_id == uid)
            )
        )
        await self.session.execute(
            update(Task).where(Task.id.in_(task_ids)).values(assignee_id=None)
        )
        await self.session.delete(member)
        await self.session.commit()
        if self.cache is not None:
            for tid in task_ids:
                await self.cache.invalidate(tid)
            for pid in await self.session.scalars(project_ids):
                await self.cache.invalidate_project(pid)

    async def project(self, pid: int, user: User, write: bool = False) -> Project:
        project = await self.projects.get(pid)
        if project is None:
            raise NotFoundException(PROJECT_NOT_FOUND)
        await self.authorize(project.workspace_id, user, write=write)
        if write and project.status == ProjectStatus.ARCHIVED:
            raise ConflictException(PROJECT_ARCHIVED)
        return project

    async def create_project(self, wid: int, data: ProjectInput, user: User) -> Project:
        await self.authorize(wid, user, write=True)
        return await self.projects.create(workspace_id=wid, **data.model_dump())

    async def update_project(self, pid: int, data: ProjectUpdate, user: User) -> Project:
        project = await self.project(pid, user)
        await self.authorize(project.workspace_id, user, write=True)
        return await self.projects.update(project, data.model_dump(exclude_unset=True))

    async def task(self, tid: int, user: User, write: bool = False) -> Task:
        task = await self.tasks.get(tid)
        if task is None or task.project_id is None:
            raise NotFoundException(PROJECT_TASK_NOT_FOUND)
        await self.project(task.project_id, user, write=write)
        return task

    async def validate_assignee(self, wid: int, uid: int | None) -> None:
        if uid is not None:
            target = await self.session.get(User, uid)
            if target is None or not target.is_active or await self.members.get(wid, uid) is None:
                raise InvalidInputException(INVALID_ASSIGNEE)

    async def create_task(self, pid: int, data: ProjectTaskCreate, user: User) -> Task:
        project = await self.project(pid, user, write=True)
        await self.validate_assignee(project.workspace_id, data.assignee_id)
        task = await self.tasks.create(
            project_id=pid,
            owner_id=user.id,
            completed=data.status == TaskStatus.DONE,
            **data.model_dump(),
        )
        if self.cache is not None:
            await self.cache.invalidate_project(pid)
        return task

    async def update_task(self, tid: int, data: ProjectTaskUpdate, user: User) -> Task:
        task = await self.task(tid, user, write=True)
        assert task.project_id is not None
        project = await self.project(task.project_id, user, write=True)
        if "assignee_id" in data.model_fields_set:
            await self.validate_assignee(project.workspace_id, data.assignee_id)
        values = data.model_dump(exclude_unset=True)
        if "status" in values:
            values["completed"] = values["status"] == TaskStatus.DONE
        result = await self.tasks.update(task, values)
        await self.invalidate_task(task)
        return result

    async def invalidate_task(self, task: Task) -> None:
        if self.cache is not None:
            await self.cache.invalidate(task.id)
            if task.project_id is not None:
                await self.cache.invalidate_project(task.project_id)

    async def delete_task(self, tid: int, user: User) -> None:
        task = await self.task(tid, user, write=True)
        await self.session.execute(delete(TaskLabel).where(TaskLabel.task_id == tid))
        await self.session.execute(delete(Comment).where(Comment.task_id == tid))
        await self.tasks.delete(task)
        await self.invalidate_task(task)

    async def create_label(self, pid: int, data: LabelInput, user: User) -> Label:
        await self.project(pid, user, write=True)
        existing = await self.session.scalar(
            select(Label).where(Label.project_id == pid, Label.name == data.name)
        )
        if existing is not None:
            raise ConflictException(LABEL_ALREADY_EXISTS)
        async with self._label_write():
            return await self.labels.create(project_id=pid, **data.model_dump())

    async def label(self, lid: int, user: User, write: bool = False) -> Label:
        label = await self.labels.get(lid)
        if label is None:
            raise NotFoundException(LABEL_NOT_FOUND)
        await self.project(label.project_id, user, write=write)
        return label

    async def attach_label(self, tid: int, lid: int, user: User, remove: bool = False) -> None:
        task = await self.task(tid, user, write=True)
        label = await self.label(lid, user, write=True)
        if label.project_id != task.project_id:
            raise InvalidInputException(LABEL_PROJECT_MISMATCH)
        link = await self.session.get(TaskLabel, (tid, lid))
        if remove and link is not None:
            await self.session.delete(link)
        elif not remove and link is None:
            self.session.add(TaskLabel(task_id=tid, label_id=lid))
        await self.session.commit()

    async def delete_project(self, pid: int, user: User) -> None:
        project = await self.project(pid, user)
        await self.authorize(project.workspace_id, user, owner=True)
        tasks = list(await self.session.scalars(select(Task).where(Task.project_id == pid)))
        tids = [task.id for task in tasks]
        await self.session.execute(delete(TaskLabel).where(TaskLabel.task_id.in_(tids)))
        await self.session.execute(delete(Comment).where(Comment.task_id.in_(tids)))
        await self.session.execute(delete(Task).where(Task.project_id == pid))
        await self.session.execute(delete(Label).where(Label.project_id == pid))
        await self.session.delete(project)
        await self.session.commit()
        for task in tasks:
            await self.invalidate_task(task)

    async def delete_workspace(self, wid: int, user: User) -> None:
        workspace = await self.authorize(wid, user, owner=True)
        # Delete all descendants in one transaction (no per-project commits).
        pids = list(
            await self.session.scalars(select(Project.id).where(Project.workspace_id == wid))
        )
        tasks = list(await self.session.scalars(select(Task).where(Task.project_id.in_(pids))))
        tids = [t.id for t in tasks]
        await self.session.execute(delete(TaskLabel).where(TaskLabel.task_id.in_(tids)))
        await self.session.execute(delete(Comment).where(Comment.task_id.in_(tids)))
        await self.session.execute(delete(Task).where(Task.project_id.in_(pids)))
        await self.session.execute(delete(Label).where(Label.project_id.in_(pids)))
        await self.session.execute(delete(Project).where(Project.id.in_(pids)))
        await self.session.execute(
            delete(WorkspaceMember).where(WorkspaceMember.workspace_id == wid)
        )
        await self.session.delete(workspace)
        await self.session.commit()
        for task in tasks:
            await self.invalidate_task(task)

    async def update_profile(self, user: User, data: ProfileUpdate) -> User:
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(user, key, value)
        try:
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            if is_unique_violation(exc, USERS_EMAIL_CONSTRAINT, "users.email"):
                raise EmailAlreadyExistsError() from exc
            raise
        return user

    async def member_list(self, wid: int, user: User) -> list[WorkspaceMember]:
        await self.authorize(wid, user)
        return list(
            await self.session.scalars(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid)
            )
        )

    async def project_page(
        self, wid: int, user: User, pagination: PaginationParams
    ) -> tuple[list[Project], int]:
        await self.authorize(wid, user)
        return await self.projects.page(
            pagination.offset, pagination.limit, Project.workspace_id == wid
        )

    async def task_page(
        self,
        pid: int,
        user: User,
        query: ProjectTaskFilters,
    ) -> Page[ProjectTaskOut]:
        await self.project(pid, user)
        if self.cache is None:
            return await self._load_task_page(pid, query)
        return await self.cache.get_or_load(
            self.cache.project_version_key(pid),
            query.model_dump(mode="json"),
            Page[ProjectTaskOut],
            lambda: self._load_task_page(pid, query),
        )

    async def _load_task_page(self, pid: int, query: ProjectTaskFilters) -> Page[ProjectTaskOut]:
        pagination = PaginationParams(page=query.page, limit=query.limit)
        filters = task_search_filters(query.search)
        filters.append(Task.project_id == pid)
        if query.status is not None:
            filters.append(Task.status == query.status)
        if query.priority is not None:
            filters.append(Task.priority == query.priority)
        if query.assignee_id is not None:
            filters.append(Task.assignee_id == query.assignee_id)
        rows, total = await self.tasks.page(pagination.offset, pagination.limit, *filters)
        return Page[ProjectTaskOut](
            items=[ProjectTaskOut.model_validate(t) for t in rows],
            total=total,
            page=pagination.page,
            limit=pagination.limit,
        )

    async def label_list(self, pid: int, user: User) -> list[Label]:
        await self.project(pid, user)
        return list(await self.session.scalars(select(Label).where(Label.project_id == pid)))

    async def update_label(self, lid: int, data: LabelInput, user: User) -> Label:
        label = await self.label(lid, user, write=True)
        existing = await self.session.scalar(
            select(Label).where(
                Label.project_id == label.project_id, Label.name == data.name, Label.id != lid
            )
        )
        if existing is not None:
            raise ConflictException(LABEL_ALREADY_EXISTS)
        async with self._label_write():
            return await self.labels.update(label, data.model_dump())

    async def delete_label(self, lid: int, user: User) -> None:
        label = await self.label(lid, user, write=True)
        await self.session.execute(delete(TaskLabel).where(TaskLabel.label_id == lid))
        await self.labels.delete(label)

    async def task_label_list(self, tid: int, user: User) -> list[Label]:
        await self.task(tid, user)
        return list(
            await self.session.scalars(
                select(Label).join(TaskLabel).where(TaskLabel.task_id == tid)
            )
        )

    async def add_comment(self, tid: int, content: str, user: User) -> Comment:
        await self.task(tid, user, write=True)
        return await self.comments.create(task_id=tid, author_id=user.id, content=content)

    async def comment_page(
        self, tid: int, user: User, pagination: PaginationParams
    ) -> tuple[list[Comment], int]:
        await self.task(tid, user)
        return await self.comments.page(pagination.offset, pagination.limit, Comment.task_id == tid)

    async def delete_comment(self, cid: int, user: User) -> None:
        comment = await self.comments.get(cid)
        if comment is None:
            raise NotFoundException(COMMENT_NOT_FOUND)
        task = await self.task(comment.task_id, user, write=True)
        if comment.author_id != user.id:
            assert task.project_id is not None
            project = await self.project(task.project_id, user)
            await self.authorize(project.workspace_id, user, owner=True)
        await self.comments.delete(comment)
