from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.enums import Priority, TaskStatus
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class Task(Base):
    __tablename__ = "tasks"

    __table_args__ = (
        CheckConstraint(
            "status IN ('TODO','IN_PROGRESS','IN_REVIEW','DONE')", name="ck_task_status"
        ),
        CheckConstraint("priority IN ('LOW','MEDIUM','HIGH','URGENT')", name="ck_task_priority"),
    )
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), index=True)
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False, length=20),
        default=TaskStatus.TODO,
        server_default=TaskStatus.TODO,
    )
    priority: Mapped[Priority] = mapped_column(
        Enum(Priority, native_enum=False, length=10),
        default=Priority.MEDIUM,
        server_default=Priority.MEDIUM,
    )
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def created_by(self) -> int:
        return self.owner_id

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )

    owner: Mapped[User] = relationship(
        back_populates="tasks",
        foreign_keys=[owner_id],
        lazy="raise",
    )
