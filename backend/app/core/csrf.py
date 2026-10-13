"""CSRF protection for cookie-authenticated requests (signed double submit)."""

from http.cookies import CookieError, SimpleCookie

from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import Settings
from app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, CSRF_HEADER, REFRESH_COOKIE
from app.core.security import is_valid_csrf_token

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _parse_cookies(header: str) -> dict[str, str]:
    jar: SimpleCookie = SimpleCookie()
    try:
        jar.load(header)
    except CookieError:
        return {}
    return {name: morsel.value for name, morsel in jar.items()}


class CSRFMiddleware:
    """Rejects state-changing API requests that ride on auth cookies without
    proving they came from our own frontend.

    Requests with no auth cookies (login, register) are let through: there is
    no session for an attacker to abuse, and SameSite=Lax already stops
    cross-site POSTs from carrying cookies.
    """

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] in SAFE_METHODS
            or not scope["path"].startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        cookies = _parse_cookies(headers.get("cookie", ""))
        if ACCESS_COOKIE not in cookies and REFRESH_COOKIE not in cookies:
            await self.app(scope, receive, send)
            return

        cookie_token = cookies.get(CSRF_COOKIE, "")
        header_token = headers.get(CSRF_HEADER, "")
        if (
            cookie_token
            and header_token == cookie_token
            and is_valid_csrf_token(self.settings, cookie_token)
        ):
            await self.app(scope, receive, send)
            return

        response = JSONResponse(
            {"detail": "CSRF token missing or invalid.", "code": "csrf_failed"}, status_code=403
        )
        await response(scope, receive, send)
