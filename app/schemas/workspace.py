from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WorkspaceRole = Literal["OWNER", "EDITOR", "VIEWER"]
TaskStatus = Literal["TODO", "IN_PROGRESS", "IN_REVIEW", "DONE"]
Priority = Literal["LOW", "MEDIUM", "HIGH", "URGENT"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Named(Input):
    name: str = Field(min_length=1, max_length=200)


class MemberInput(Input):
    user_id: int = Field(gt=0)
    role: Literal["EDITOR", "VIEWER"] = "VIEWER"


class MemberUpdate(Input):
    role: Literal["EDITOR", "VIEWER"]


class ProjectInput(Named):
    description: str = Field(default="", max_length=10000)


class ProjectUpdate(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: Literal["ACTIVE", "ARCHIVED"] | None = None

    @model_validator(mode="after")
    def non_null(self) -> "ProjectUpdate":
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Omit unchanged fields instead of null")
        return self


class LabelInput(Input):
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#808080", pattern=r"^#[0-9a-fA-F]{6}$")


class CommentInput(Input):
    content: str = Field(min_length=1, max_length=10000)


class ProjectTaskCreate(Input):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=10000)
    assignee_id: int | None = Field(default=None, gt=0)
    status: TaskStatus = "TODO"
    priority: Priority = "MEDIUM"
    due_date: datetime | None = None


class ProjectTaskUpdate(Input):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    assignee_id: int | None = Field(default=None, gt=0)
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: datetime | None = None

    @model_validator(mode="after")
    def non_null(self) -> "ProjectTaskUpdate":
        for name in self.model_fields_set - {"assignee_id", "due_date"}:
            if getattr(self, name) is None:
                raise ValueError("Omit unchanged fields instead of null")
        return self


class Output(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorkspaceOut(Output):
    id: int
    name: str
    owner_id: int
    created_at: datetime


class MemberOut(Output):
    workspace_id: int
    user_id: int
    role: WorkspaceRole


class ProjectOut(Output):
    id: int
    workspace_id: int
    name: str
    description: str
    status: str
    created_at: datetime


class LabelOut(Output):
    id: int
    project_id: int
    name: str
    color: str


class CommentOut(Output):
    id: int
    task_id: int
    author_id: int
    content: str
    created_at: datetime


class ProjectTaskOut(Output):
    id: int
    project_id: int | None
    created_by: int
    assignee_id: int | None
    title: str
    description: str
    status: str
    priority: str
    due_date: datetime | None
    created_at: datetime


class ProjectTaskPage(BaseModel):
    items: list[ProjectTaskOut]
    total: int
    page: int
    limit: int
