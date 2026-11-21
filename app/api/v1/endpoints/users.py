from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.database import Session
from app.core.messages import ACCESS_FORBIDDEN, INVALID_AUTH_CREDENTIALS
from app.core.permissions import require_role
from app.models.enums import UserRole
from app.repositories.user import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.pagination import Page, Pagination
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def get_user_service(session: Session) -> UserService:
    return UserService(UserRepository(session))


UserServiceDependency = Annotated[UserService, Depends(get_user_service)]


@router.get(
    "",
    response_model=Page[UserResponse],
    summary="List users as an administrator",
    dependencies=[Depends(require_role(UserRole.ADMIN))],
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": INVALID_AUTH_CREDENTIALS},
        status.HTTP_403_FORBIDDEN: {"description": ACCESS_FORBIDDEN},
    },
)
async def list_users(service: UserServiceDependency, pagination: Pagination) -> Page[UserResponse]:
    users, total = await service.page(pagination)
    return Page[UserResponse](
        items=[UserResponse.model_validate(user) for user in users],
        total=total,
        offset=pagination.offset,
        limit=pagination.limit,
    )
