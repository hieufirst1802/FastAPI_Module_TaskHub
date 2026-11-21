from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import TITLE_MAX_LENGTH
from app.models.base import Base
from app.models.enums import TaskStatus

if TYPE_CHECKING:
    from app.models.user import User


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(TITLE_MAX_LENGTH))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status", native_enum=False, create_constraint=True),
        default=TaskStatus.TODO,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", name="fk_tasks_owner_id_users", ondelete="CASCADE"),
        index=True,
    )

    owner: Mapped[User] = relationship(
        back_populates="tasks",
        lazy="raise",
    )
