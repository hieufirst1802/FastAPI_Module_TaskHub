from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./tasks.db"
    jwt_secret: str = Field(min_length=32)
    token_minutes: int = Field(default=30, ge=1, le=1440)
    redis_url: str | None = None
    cache_seconds: int = Field(default=60, ge=1)

    @model_validator(mode="after")
    def production(self) -> "Settings":
        if self.environment == "production" and not self.redis_url:
            raise ValueError("Production requires REDIS_URL")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Required secret is loaded from environment.
