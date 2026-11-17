from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    status: Mapped[str] = mapped_column(String(20), default="TODO", server_default="TODO")
    priority: Mapped[str] = mapped_column(String(10), default="MEDIUM", server_default="MEDIUM")
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
