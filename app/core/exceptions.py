from collections.abc import Mapping
from typing import ClassVar

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.messages import USERNAME_ALREADY_REGISTERED


class AppException(Exception):
    status_code: int
    headers: ClassVar[Mapping[str, str] | None] = None


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN


class UsernameAlreadyExistsError(ConflictException):
    def __init__(self) -> None:
        super().__init__(USERNAME_ALREADY_REGISTERED)


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    headers: ClassVar[Mapping[str, str] | None] = {"WWW-Authenticate": "Bearer"}


async def handle_app_exception(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppException)
    return JSONResponse(
        status_code=exc.status_code, content={"detail": str(exc)}, headers=exc.headers
    )
