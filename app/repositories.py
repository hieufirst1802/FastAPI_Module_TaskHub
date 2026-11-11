from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.models import Base, User


class BaseRepository[T: Base]:
    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def get(self, identifier: int) -> T | None:
        return await self.session.get(self.model, identifier)

    async def page(
        self, offset: int, limit: int, *filters: ColumnElement[bool]
    ) -> tuple[list[T], int]:
        total = await self.session.scalar(
            select(func.count()).select_from(self.model).where(*filters)
        )
        rows = await self.session.scalars(
            select(self.model)
            .where(*filters)
            .order_by(self.model.__table__.c.id)
            .offset(offset)
            .limit(limit)
        )
        return list(rows), int(total or 0)

    async def create(self, **values: Any) -> T:
        entity = self.model(**values)
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: T, values: dict[str, Any]) -> T:
        for key, value in values.items():
            setattr(entity, key, value)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.commit()


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def by_username(self, username: str) -> User | None:
        return await self.session.scalar(select(User).where(User.username == username))
