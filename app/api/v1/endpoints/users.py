from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.database import Session
from app.core.permissions import require_role
from app.enums import UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.pagination import UserPage
from app.services.user import UserService

router = APIRouter(prefix="/api/users", tags=["Users"])


def get_user_service(session: Session) -> UserService:
    return UserService(UserRepository(session))


UserServiceDependency = Annotated[
    UserService,
    Depends(get_user_service),
]

AdminUser = Annotated[
    object,
    Depends(require_role(UserRole.ADMIN)),
]


@router.get("", response_model=UserPage)
async def page(
    service: UserServiceDependency,
    admin: AdminUser,
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> UserPage:
    users, total = await service.page(offset, limit)

    return UserPage(
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        offset=offset,
        limit=limit,
    )
