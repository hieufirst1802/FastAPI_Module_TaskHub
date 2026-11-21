from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_JWT_SECRETS = {
    "dev-only-change-this-secret-key-2026",
    "local-compose-change-this-secret-key-before-deploying",
    "replace-with-a-long-random-secret",
}


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
    jwt_algorithm: Literal["HS256"] = "HS256"
    access_token_expire_minutes: int = Field(default=30, ge=1)

    @model_validator(mode="after")
    def validate_deployed_jwt_secret(self) -> "Settings":
        if self.environment.strip().lower() in {"production", "staging"}:
            secret = self.jwt_secret_key
            if len(secret.strip()) < 32 or secret.strip() in DEVELOPMENT_JWT_SECRETS:
                raise ValueError("JWT_SECRET_KEY must be a unique secret of at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
