from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "FastAPI Practice"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api/v1"

    database_url: str = "sqlite+aiosqlite:///./data/app.db"
    database_echo: bool = False

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
