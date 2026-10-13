"""The three auth cookies, set and cleared in one place.

- access:  short-lived JWT, httpOnly, sent on every request.
- refresh: opaque rotating token, httpOnly, scoped to the auth endpoints so it
  is not sent (or exposed) on ordinary API calls.
- csrf:    readable by JavaScript, echoed back in a header (double submit).
"""

from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "mp_access"
REFRESH_COOKIE = "mp_refresh"
CSRF_COOKIE = "mp_csrf"
CSRF_HEADER = "x-csrf-token"

REFRESH_PATH = "/api/v1/auth"


def set_auth_cookies(
    response: Response,
    settings: Settings,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    secure = settings.secure_cookies
    refresh_max_age = settings.refresh_token_ttl_days * 24 * 3600
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.access_token_ttl_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=refresh_max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_PATH,
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=refresh_max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    secure = settings.secure_cookies
    response.delete_cookie(ACCESS_COOKIE, path="/", secure=secure, httponly=True, samesite="lax")
    response.delete_cookie(
        REFRESH_COOKIE, path=REFRESH_PATH, secure=secure, httponly=True, samesite="lax"
    )
    response.delete_cookie(CSRF_COOKIE, path="/", secure=secure, samesite="lax")
