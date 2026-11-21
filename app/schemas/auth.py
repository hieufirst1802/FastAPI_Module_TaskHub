from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.enums import UserRole


class RegisterRequest(BaseModel):
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    full_name: str = Field(default="", max_length=200)
    username: str = Field(
        min_length=3,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$",
    )
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class LoginRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{"username": "demo_member", "password": "ExamplePassword123!"}]
        }
    )

    username: str = Field(
        min_length=3,
        max_length=50,
    )
    password: str = Field(
        min_length=8,
        max_length=128,
    )


class TokenResponse(BaseModel):
    refresh_token: str = Field(description="Token used for refresh or logout.")
    access_token: str = Field(description="JWT used in the Authorization Bearer header.")
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: UserRole
    email: str | None = None
    full_name: str = ""
    is_active: bool = True
    created_at: datetime | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(
        min_length=1, max_length=4096, description="Refresh token from login or rotation."
    )


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    full_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @model_validator(mode="after")
    def non_null(self) -> "ProfileUpdate":
        if any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Omit unchanged fields instead of null")
        return self


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
