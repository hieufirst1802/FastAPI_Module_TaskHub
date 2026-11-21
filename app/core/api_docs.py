from typing import Any

from pydantic import BaseModel

from app.core.enums import ErrorCode


class ErrorDetail(BaseModel):
    code: ErrorCode
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


class ValidationIssue(BaseModel):
    loc: list[str | int]
    msg: str
    type: str


class ValidationErrorDetail(ErrorDetail):
    details: list[ValidationIssue] | None = None


class ValidationErrorResponse(BaseModel):
    error: ValidationErrorDetail


ERROR_DESCRIPTIONS = {
    400: "The request could not be applied.",
    401: "Credentials are missing, invalid, expired, or revoked.",
    403: "The account does not have permission to perform this operation.",
    404: "The resource does not exist or is not visible to this account.",
    409: "The operation conflicts with the current state of the resource.",
    422: "The request failed field validation or a domain input rule.",
    500: "An unexpected server error occurred.",
}


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    responses: dict[int | str, dict[str, Any]] = {}
    for code in status_codes:
        response: dict[str, Any] = {
            "description": ERROR_DESCRIPTIONS[code],
            "model": ValidationErrorResponse if code == 422 else ErrorResponse,
        }
        if code == 401:
            response["headers"] = {
                "WWW-Authenticate": {"schema": {"type": "string", "example": "Bearer"}}
            }
        responses[code] = response
    return responses
