"""Application settings, read from the environment (and a local `.env` in dev)."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent

INSECURE_DEV_SECRET = "dev-only-secret-change-me-in-production-0123456789"  # noqa: S105


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

    # Where the app is reached by browsers. Used for links in emails and for
    # the Google OAuth redirect. In dev this is the Vite dev server.
    public_base_url: str = "http://localhost:5173"

    # --- Auth ---------------------------------------------------------------
    secret_key: SecretStr = SecretStr(INSECURE_DEV_SECRET)
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30
    # Two tabs can refresh at the same moment; within this window a second use
    # of the same refresh token is treated as that race, not as theft.
    refresh_reuse_grace_seconds: int = 10
    email_verify_ttl_hours: int = 48
    password_reset_ttl_minutes: int = 60
    max_failed_logins: int = 5
    lockout_minutes: int = 15
    # None means "Secure cookies in prod only", so http://localhost works in dev.
    cookie_secure: bool | None = None

    google_client_id: str | None = None
    google_client_secret: SecretStr | None = None

    # --- Rate limits (slowapi syntax) ---------------------------------------
    rate_limit_enabled: bool = True
    rate_limit_auth: str = "10/minute"
    rate_limit_email: str = "5/hour"
    rate_limit_default: str = "120/minute"

    # --- Email --------------------------------------------------------------
    # With no SMTP host, emails are written to the log instead of being sent.
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = True
    email_from: str = "Mentor Pilot <no-reply@mentorpilot.local>"

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _use_asyncpg_driver(cls, value: str) -> str:
        # Hosting providers hand out `postgres://` / `postgresql://` URLs.
        for prefix in ("postgres://", "postgresql://"):
            if value.startswith(prefix):
                return "postgresql+asyncpg://" + value[len(prefix) :]
        return value

    @model_validator(mode="after")
    def _require_real_secret_in_prod(self) -> Self:
        if self.is_prod and self.secret_key.get_secret_value() == INSECURE_DEV_SECRET:
            raise ValueError("SECRET_KEY must be set to a long random value in production")
        return self

    @property
    def secure_cookies(self) -> bool:
        return self.is_prod if self.cookie_secure is None else self.cookie_secure

    @property
    def google_oauth_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"

    @property
    def is_prod(self) -> bool:
        return self.environment == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()
