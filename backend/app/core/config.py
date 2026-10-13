"""Application settings, read from the environment (and a local `.env` in dev)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Mentor Pilot"
    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://mentor:mentor@localhost:5432/mentor_pilot"
    test_database_url: str = "postgresql+asyncpg://mentor:mentor@localhost:5432/mentor_pilot_test"
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_connect_timeout_seconds: float = 5.0
    redis_url: str | None = None

    # Only used in dev, where the Vite dev server is a different origin. In prod
    # the SPA is served by this app, so everything is same-origin.
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])

    static_dir: Path = BACKEND_DIR / "app" / "static"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _use_asyncpg_driver(cls, value: str) -> str:
        # Hosting providers hand out `postgres://` / `postgresql://` URLs.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
