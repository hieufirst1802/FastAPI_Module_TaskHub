from collections.abc import Mapping
from typing import ClassVar

from fastapi import status

from app.core.enums import ErrorCode
from app.core.messages import USERNAME_ALREADY_REGISTERED


class AppException(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = ErrorCode.APPLICATION_ERROR
    headers: ClassVar[Mapping[str, str] | None] = None


class NotFoundException(AppException):
    status_code = status.HTTP_404_NOT_FOUND
    code = ErrorCode.NOT_FOUND


class ConflictException(AppException):
    status_code = status.HTTP_409_CONFLICT
    code = ErrorCode.CONFLICT


class ForbiddenException(AppException):
    status_code = status.HTTP_403_FORBIDDEN
    code = ErrorCode.FORBIDDEN


class UsernameAlreadyExistsError(ConflictException):
    code = ErrorCode.USERNAME_ALREADY_EXISTS

    def __init__(self) -> None:
        super().__init__(USERNAME_ALREADY_REGISTERED)


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = ErrorCode.UNAUTHORIZED
    headers: ClassVar[Mapping[str, str] | None] = {"WWW-Authenticate": "Bearer"}
