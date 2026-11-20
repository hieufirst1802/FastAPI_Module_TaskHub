from collections.abc import Mapping
from http import HTTPStatus
from typing import ClassVar

from fastapi import status

from app.core.enums import ErrorCode
from app.core.messages import EMAIL_ALREADY_REGISTERED, USERNAME_ALREADY_REGISTERED


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


class EmailAlreadyExistsError(ConflictException):
    code = ErrorCode.EMAIL_ALREADY_EXISTS

    def __init__(self) -> None:
        super().__init__(EMAIL_ALREADY_REGISTERED)


class InvalidInputException(AppException):
    status_code = HTTPStatus.UNPROCESSABLE_ENTITY
    code = ErrorCode.VALIDATION_ERROR


class BadRequestException(AppException):
    status_code = status.HTTP_400_BAD_REQUEST
    code = ErrorCode.BAD_REQUEST


class UnauthorizedException(AppException):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = ErrorCode.UNAUTHORIZED
    headers: ClassVar[Mapping[str, str] | None] = {"WWW-Authenticate": "Bearer"}
