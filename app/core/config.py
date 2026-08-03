from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Practice"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    database_echo: bool = False

    secret_key: str = "development-secret-key-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

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
