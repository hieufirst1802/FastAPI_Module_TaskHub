from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    environment: str = "development"
    database_url: str = "sqlite+aiosqlite:///./tasks.db"

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    redis_cache_ttl: int = Field(default=60, ge=1)
    redis_socket_timeout: float = Field(default=0.2, gt=0)
    redis_key_prefix: str = "taskhub:v1"

    # JWT configuration
    jwt_secret_key: str = "dev-only-change-this-secret-key-2026"
    refresh_token_expire_days: int = Field(default=7, ge=1)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
