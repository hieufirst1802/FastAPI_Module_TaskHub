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
