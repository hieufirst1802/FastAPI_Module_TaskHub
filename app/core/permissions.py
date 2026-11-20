from collections.abc import Awaitable, Callable

from app.core.dependencies import CurrentUser
from app.core.exceptions import ForbiddenException
from app.core.messages import ACCESS_FORBIDDEN
from app.models.enums import UserRole
from app.models.user import User


def require_role(
    *allowed_roles: UserRole,
) -> Callable[[User], Awaitable[User]]:
    """Create a dependency that checks the current user's role."""

    async def role_checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(ACCESS_FORBIDDEN)

        return current_user

    return role_checker
