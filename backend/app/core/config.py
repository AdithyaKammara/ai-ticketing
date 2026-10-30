from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, PostgresDsn, RedisDsn, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-only configuration. Missing required values stop the app at startup."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    database_url: PostgresDsn
    redis_url: RedisDsn
    jwt_secret: SecretStr = Field(min_length=32)
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    # Browsers treat localhost as secure, so Secure cookies work in local development too.
    cookie_secure: bool = True
    allow_registration: bool = True
    login_max_failures: int = 5
    login_lockout_seconds: int = 15 * 60
    ticket_create_limit_per_hour: int = 10

    # Only the worker calls the LLM, so the API can start without a key; the worker cannot.
    groq_api_key: SecretStr | None = None
    llm_model: str = "llama-3.3-70b-versatile"
    auto_resolve_min_confidence: int = Field(default=85, ge=0, le=100)
    # Model calls per UTC day across all users; past it, tickets skip AI and go to a person.
    llm_daily_budget: int = Field(default=500, ge=0)
    auto_close_after_days: int = 7
    triage_log_retention_days: int = 90

    sentry_dsn: SecretStr | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
