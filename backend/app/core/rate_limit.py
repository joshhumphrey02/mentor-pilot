"""Rate limiting with slowapi: Redis-backed when REDIS_URL is set, else in-memory."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_settings.redis_url or "memory://",
    default_limits=[_settings.rate_limit_default],
    enabled=_settings.rate_limit_enabled,
    # If Redis goes down, fall back to per-process limits rather than failing requests.
    in_memory_fallback_enabled=bool(_settings.redis_url),
)

AUTH_LIMIT = _settings.rate_limit_auth
EMAIL_LIMIT = _settings.rate_limit_email


def _rate_limited(_request: Request, exc: Exception) -> Response:
    assert isinstance(exc, RateLimitExceeded)  # noqa: S101
    return JSONResponse(
        {
            "detail": "Too many requests. Please wait a moment and try again.",
            "code": "rate_limited",
        },
        status_code=429,
        headers={"Retry-After": "60"},
    )


def register_rate_limiter(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limited)
