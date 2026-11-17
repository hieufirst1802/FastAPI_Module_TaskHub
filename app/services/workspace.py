from fastapi import HTTPException
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import TaskCache
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Comment, Label, Project, TaskLabel, Workspace, WorkspaceMember
from app.repositories.workspace import DomainRepository, MembershipRepository
from app.schemas.auth import ProfileUpdate
from app.schemas.workspace import (
    LabelInput,
    Priority,
    ProjectInput,
    ProjectTaskCreate,
    ProjectTaskOut,
    ProjectTaskPage,
    ProjectTaskUpdate,
    ProjectUpdate,
    TaskStatus,
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

    async def authorize(
        self, workspace_id: int, user: User, write: bool = False, owner: bool = False
    ) -> Workspace:
        workspace = await self.workspaces.get(workspace_id)
        if workspace is None:
            raise HTTPException(404, "Workspace not found")
        if user.role.lower() == "admin":
            return workspace
        member = await self.members.get(workspace_id, user.id)
        if member is None:
            raise HTTPException(404, "Workspace not found")
        if (owner and member.role != "OWNER") or (write and member.role == "VIEWER"):
            raise HTTPException(403, "Insufficient workspace role")
        return workspace

    async def workspace_page(
        self, user: User, offset: int, limit: int
    ) -> tuple[list[Workspace], int]:
        if user.role.lower() == "admin":
            return await self.workspaces.page(offset, limit)
        ids = select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
        return await self.workspaces.page(offset, limit, Workspace.id.in_(ids))

    async def create_workspace(self, name: str, user: User) -> Workspace:
        workspace = Workspace(name=name, owner_id=user.id)
        self.session.add(workspace)
        await self.session.flush()
        self.session.add(WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role="OWNER"))
        await self.session.commit()
        await self.session.refresh(workspace)
        return workspace

    async def set_member(
        self, wid: int, uid: int, role: str, user: User, require_existing: bool = False
    ) -> WorkspaceMember:
        workspace = await self.authorize(wid, user, owner=True)
        if uid == workspace.owner_id:
            raise HTTPException(409, "Workspace owner role cannot be changed")
        target = await self.session.get(User, uid)
        if target is None or not target.is_active:
            raise HTTPException(404, "Active user not found")
        member = await self.members.get(wid, uid)
        if require_existing and member is None:
            raise HTTPException(404, "Member not found")
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
            raise HTTPException(409, "Cannot remove workspace owner")
        member = await self.members.get(wid, uid)
        if member is None:
            raise HTTPException(404, "Member not found")
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
            raise HTTPException(404, "Project not found")
        await self.authorize(project.workspace_id, user, write=write)
        if write and project.status == "ARCHIVED":
            raise HTTPException(409, "Project is archived")
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
            raise HTTPException(404, "Project task not found")
        await self.project(task.project_id, user, write=write)
        return task

    async def validate_assignee(self, wid: int, uid: int | None) -> None:
        if uid is not None:
            target = await self.session.get(User, uid)
            if target is None or not target.is_active or await self.members.get(wid, uid) is None:
                raise HTTPException(422, "Assignee must be an active workspace member")

    async def create_task(self, pid: int, data: ProjectTaskCreate, user: User) -> Task:
        project = await self.project(pid, user, write=True)
        await self.validate_assignee(project.workspace_id, data.assignee_id)
        task = await self.tasks.create(
            project_id=pid, owner_id=user.id, completed=data.status == "DONE", **data.model_dump()
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
            values["completed"] = values["status"] == "DONE"
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
            raise HTTPException(409, "Label name already exists in project")
        return await self.labels.create(project_id=pid, **data.model_dump())

    async def label(self, lid: int, user: User, write: bool = False) -> Label:
        label = await self.labels.get(lid)
        if label is None:
            raise HTTPException(404, "Label not found")
        await self.project(label.project_id, user, write=write)
        return label

    async def attach_label(self, tid: int, lid: int, user: User, remove: bool = False) -> None:
        task = await self.task(tid, user, write=True)
        label = await self.label(lid, user, write=True)
        if label.project_id != task.project_id:
            raise HTTPException(422, "Label and task must belong to the same project")
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
        await self.session.commit()
        return user

    async def member_list(self, wid: int, user: User) -> list[WorkspaceMember]:
        await self.authorize(wid, user)
        return list(
            await self.session.scalars(
                select(WorkspaceMember).where(WorkspaceMember.workspace_id == wid)
            )
        )

    async def project_page(self, wid: int, user: User, page: int, limit: int) -> list[Project]:
        await self.authorize(wid, user)
        rows, _ = await self.projects.page((page - 1) * limit, limit, Project.workspace_id == wid)
        return rows

    async def task_page(
        self,
        pid: int,
        user: User,
        page: int,
        limit: int,
        status: TaskStatus | None,
        priority: Priority | None,
        assignee_id: int | None,
    ) -> ProjectTaskPage:
        await self.project(pid, user)
        cache = self.cache
        version = await cache.project_version(pid) if cache is not None else None
        key = f"{cache.prefix if cache else ''}:projects:{pid}:tasks:{version}:{page}:{limit}:{status}:{priority}:{assignee_id}"
        if cache is not None and version is not None:
            cached = await cache.get_page(key)
            if cached is not None:
                return cached
        filters = [Task.project_id == pid]
        if status is not None:
            filters.append(Task.status == status)
        if priority is not None:
            filters.append(Task.priority == priority)
        if assignee_id is not None:
            filters.append(Task.assignee_id == assignee_id)
        rows, total = await self.tasks.page((page - 1) * limit, limit, *filters)
        result = ProjectTaskPage(
            items=[ProjectTaskOut.model_validate(t) for t in rows],
            total=total,
            page=page,
            limit=limit,
        )
        if cache is not None and version is not None:
            await cache.set_page(key, result)
        return result

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
            raise HTTPException(409, "Label name already exists in project")
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

    async def comment_page(self, tid: int, user: User, page: int, limit: int) -> list[Comment]:
        await self.task(tid, user)
        rows, _ = await self.comments.page((page - 1) * limit, limit, Comment.task_id == tid)
        return rows

    async def delete_comment(self, cid: int, user: User) -> None:
        comment = await self.comments.get(cid)
        if comment is None:
            raise HTTPException(404, "Comment not found")
        task = await self.task(comment.task_id, user, write=True)
        if comment.author_id != user.id:
            assert task.project_id is not None
            project = await self.project(task.project_id, user)
            await self.authorize(project.workspace_id, user, owner=True)
        await self.comments.delete(comment)
