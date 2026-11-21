from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base
from app.models.workspace import WorkspaceMember
from app.repositories.base import BaseRepository


class DomainRepository[T: Base](BaseRepository[T]):
    """Shared typed CRUD; authorization stays in the service layer."""


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        return await self.session.get(WorkspaceMember, (workspace_id, user_id))
