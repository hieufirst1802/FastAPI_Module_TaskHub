from enum import StrEnum


class ErrorCode(StrEnum):
    APPLICATION_ERROR = "application_error"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    USERNAME_ALREADY_EXISTS = "username_already_exists"
    VALIDATION_ERROR = "validation_error"
    BAD_REQUEST = "bad_request"
    EMAIL_ALREADY_EXISTS = "email_already_exists"
    HTTP_ERROR = "http_error"
    INTERNAL_SERVER_ERROR = "internal_server_error"
