from pydantic import BaseModel, Field

from app.core.constants import (
    LOGIN_MIN_LENGTH,
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    USERNAME_MAX_LENGTH,
    USERNAME_MIN_LENGTH,
    USERNAME_PATTERN,
)
from app.models.enums import UserRole
from app.schemas.base import BaseSchema


class RegisterRequest(BaseModel):
    username: str = Field(
        min_length=USERNAME_MIN_LENGTH, max_length=USERNAME_MAX_LENGTH, pattern=USERNAME_PATTERN
    )
    password: str = Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)


class LoginRequest(BaseModel):
    username: str = Field(min_length=LOGIN_MIN_LENGTH)
    password: str = Field(min_length=LOGIN_MIN_LENGTH)


class TokenResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseSchema):
    id: int
    username: str
    role: UserRole
