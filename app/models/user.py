from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum, String, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import USERNAME_MAX_LENGTH
from app.models.base import Base
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.task import Task


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(
        String(USERNAME_MAX_LENGTH),
        unique=True,
        index=True,
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda roles: [role.value for role in roles],
        ),
        default=UserRole.MEMBER,
    )

    tasks: Mapped[list[Task]] = relationship(
        back_populates="owner",
        cascade="all, delete",
        passive_deletes=True,
        lazy="raise",
    )
