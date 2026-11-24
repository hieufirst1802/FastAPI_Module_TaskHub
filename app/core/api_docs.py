from typing import Any

from app.core.messages import ERROR_DESCRIPTIONS
from app.schemas.error import ErrorResponse, ValidationErrorResponse


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
