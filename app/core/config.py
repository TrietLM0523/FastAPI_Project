from functools import lru_cache
from typing import Annotated, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnvironment = Literal["development", "test", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class Settings(BaseSettings):
    app_name: str = "TaskHub API"
    app_version: str = "1.0.0"
    app_description: str = (
        "Collaborative workspace, project, task, label, and comment management API."
    )
    debug: bool = True
    app_env: AppEnvironment = "development"
    log_level: LogLevel = "INFO"
    api_prefix: str = Field(
        default="/api/v1",
        validation_alias=AliasChoices(
            "API_V1_PREFIX", "API_PREFIX", "api_v1_prefix", "api_prefix"
        ),
    )
    allowed_hosts: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "test"]
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        validation_alias=AliasChoices(
            "BACKEND_CORS_ORIGINS",
            "CORS_ORIGINS",
            "backend_cors_origins",
            "cors_origins",
        ),
    )

    database_url: str = Field(default="sqlite+aiosqlite:///./data/app.db", min_length=1)
    database_echo: bool = False

    secret_key: str = Field(
        default="development-secret-key-change-me",
        min_length=32,
        validation_alias=AliasChoices(
            "JWT_SECRET_KEY", "SECRET_KEY", "jwt_secret_key", "secret_key"
        ),
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)
    refresh_token_expire_days: int = Field(default=30, gt=0)

    redis_url: str = "redis://localhost:6379/0"
    cache_enabled: bool = True
    cache_fail_fast: bool = False
    task_list_cache_ttl_seconds: int = Field(default=60, gt=0)

    email_backend: Literal["logging"] = "logging"

    @field_validator("debug", mode="before")
    @classmethod
    def parse_debug_mode(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.lower()
            if normalized in {"release", "production", "prod"}:
                return False
            if normalized in {"development", "dev"}:
                return True

        return value

    @field_validator("allowed_hosts", "cors_origins", mode="before")
    @classmethod
    def parse_list_fields(cls, value: object) -> list[str] | object:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]
        return value

    @field_validator("app_env", mode="before")
    @classmethod
    def normalize_app_env(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().upper()
        return value

    @model_validator(mode="after")
    def validate_runtime_security(self) -> "Settings":
        if self.app_env == "production" or not self.debug:
            if self.secret_key == "development-secret-key-change-me":
                raise ValueError(
                    "Production settings require a non-default secret_key value. "
                    "Set SECRET_KEY to a unique secret for this environment."
                )
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
