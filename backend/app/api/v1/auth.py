from typing import Annotated
from urllib.parse import urlencode

import structlog
from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse

from app.api.deps import MailerDep, SessionDep, SettingsDep
from app.core.config import Settings
from app.core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.errors import (
    AppError,
    ErrorResponse,
    NotAuthenticatedError,
    NotFoundError,
    error_responses,
)
from app.core.rate_limit import AUTH_LIMIT, EMAIL_LIMIT, limiter
from app.core.security import create_signed_state, read_signed_state
from app.schemas.auth import (
    AuthProvidersResponse,
    EmailRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    TokenRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserOut
from app.services import auth as auth_service
from app.services import google_oauth, sessions
from app.services.sessions import SessionTokens

router = APIRouter(prefix="/auth", tags=["auth"])
logger = structlog.get_logger(__name__)

OAUTH_STATE_COOKIE = "mp_oauth"
OAUTH_STATE_TTL_SECONDS = 600
GOOGLE_CALLBACK_PATH = "/api/v1/auth/google/callback"

ERRORS = error_responses(400, 401, 403, 429)

# Deliberately identical whether or not the address has an account.
CHECK_EMAIL = "If that email address can be used, we've sent a message to it. Check your inbox."


def _apply(response: Response, settings: Settings, tokens: SessionTokens) -> None:
    set_auth_cookies(
        response,
        settings,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        csrf_token=tokens.csrf_token,
    )


@router.get("/providers", response_model=AuthProvidersResponse)
async def providers(settings: SettingsDep) -> AuthProvidersResponse:
    """Which sign-in methods are configured, so the UI only offers working ones."""
    return AuthProvidersResponse(google=settings.google_oauth_enabled)


@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
)
@limiter.limit(AUTH_LIMIT)
async def register(
    request: Request,
    body: RegisterRequest,
    session: SessionDep,
    settings: SettingsDep,
    mailer: MailerDep,
) -> MessageResponse:
    await auth_service.register(
        session,
        settings,
        mailer,
        email_address=body.email,
        password=body.password,
        full_name=body.full_name,
    )
    return MessageResponse(message=CHECK_EMAIL)


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
)
@limiter.limit(EMAIL_LIMIT)
async def resend_verification(
    request: Request,
    body: EmailRequest,
    session: SessionDep,
    settings: SettingsDep,
    mailer: MailerDep,
) -> MessageResponse:
    await auth_service.resend_verification(session, settings, mailer, email_address=body.email)
    return MessageResponse(message=CHECK_EMAIL)


@router.post("/verify-email", response_model=UserOut, responses=ERRORS)
@limiter.limit(AUTH_LIMIT)
async def verify_email(
    request: Request,
    response: Response,
    body: TokenRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> UserOut:
    user, tokens = await auth_service.verify_email(
        session, settings, token=body.token, user_agent=request.headers.get("user-agent")
    )
    _apply(response, settings, tokens)
    return UserOut.model_validate(user)


@router.post("/login", response_model=UserOut, responses=ERRORS)
@limiter.limit(AUTH_LIMIT)
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> UserOut:
    user, tokens = await auth_service.login(
        session,
        settings,
        email_address=body.email,
        password=body.password,
        user_agent=request.headers.get("user-agent"),
    )
    _apply(response, settings, tokens)
    return UserOut.model_validate(user)


@router.post("/refresh", response_model=UserOut, responses=ERRORS)
@limiter.limit("60/minute")
async def refresh(
    request: Request, response: Response, session: SessionDep, settings: SettingsDep
) -> UserOut | JSONResponse:
    """Swaps the refresh cookie for a new one and issues a fresh access token."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise NotAuthenticatedError("Please log in to continue.")
    try:
        user, tokens = await sessions.rotate_session(
            session, settings, raw, user_agent=request.headers.get("user-agent")
        )
    except NotAuthenticatedError as exc:
        # Returned (not raised) so the response can also tell the browser to
        # drop its dead cookies; cookies set on `response` are lost on a raise.
        failed = JSONResponse(
            ErrorResponse(detail=exc.detail, code=exc.code).model_dump(),
            status_code=exc.status_code,
        )
        clear_auth_cookies(failed, settings)
        return failed
    _apply(response, settings, tokens)
    return UserOut.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, session: SessionDep, settings: SettingsDep) -> Response:
    await sessions.end_session(session, request.cookies.get(REFRESH_COOKIE))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    clear_auth_cookies(response, settings)
    return response


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERRORS,
)
@limiter.limit(EMAIL_LIMIT)
async def forgot_password(
    request: Request,
    body: EmailRequest,
    session: SessionDep,
    settings: SettingsDep,
    mailer: MailerDep,
) -> MessageResponse:
    await auth_service.forgot_password(session, settings, mailer, email_address=body.email)
    return MessageResponse(message=CHECK_EMAIL)


@router.post("/reset-password", response_model=MessageResponse, responses=ERRORS)
@limiter.limit(AUTH_LIMIT)
async def reset_password(
    request: Request,
    response: Response,
    body: ResetPasswordRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> MessageResponse:
    await auth_service.reset_password(session, token=body.token, password=body.password)
    # Every session was just revoked, including this browser's, if it had one.
    clear_auth_cookies(response, settings)
    return MessageResponse(message="Your password has been changed. You can log in now.")


def _google_client(request: Request, settings: Settings) -> google_oauth.GoogleOAuthClient:
    client: google_oauth.GoogleOAuthClient | None = request.app.state.google_oauth
    if client is None or not settings.google_oauth_enabled:
        raise NotFoundError("Google sign-in is not set up.", code="google_not_configured")
    return client


def _login_error_redirect(settings: Settings, code: str) -> RedirectResponse:
    response = RedirectResponse(
        f"{settings.public_base_url}/login?{urlencode({'error': code})}",
        status_code=status.HTTP_303_SEE_OTHER,
    )
    response.delete_cookie(OAUTH_STATE_COOKIE, path=GOOGLE_CALLBACK_PATH)
    return response


@router.get("/google/login", include_in_schema=False)
@limiter.limit(AUTH_LIMIT)
async def google_login(request: Request, settings: SettingsDep) -> RedirectResponse:
    client = _google_client(request, settings)
    authorization = client.authorization_request(
        f"{settings.public_base_url}{GOOGLE_CALLBACK_PATH}"
    )
    response = RedirectResponse(authorization.url, status_code=status.HTTP_303_SEE_OTHER)
    # State and the PKCE verifier ride in a signed, httpOnly cookie that is only
    # sent back to the callback, so no server-side session store is needed.
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        create_signed_state(
            settings,
            {"state": authorization.state, "verifier": authorization.code_verifier},
            ttl_seconds=OAUTH_STATE_TTL_SECONDS,
        ),
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=settings.secure_cookies,
        samesite="lax",
        path=GOOGLE_CALLBACK_PATH,
    )
    return response


@router.get("/google/callback", include_in_schema=False)
@limiter.limit(AUTH_LIMIT)
async def google_callback(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=512)] = None,
) -> RedirectResponse:
    client = _google_client(request, settings)
    saved = read_signed_state(settings, request.cookies.get(OAUTH_STATE_COOKIE, ""))
    if not code or not state or saved is None or saved.get("state") != state:
        return _login_error_redirect(settings, "google_failed")

    try:
        profile = await client.fetch_profile(
            code=code,
            code_verifier=str(saved["verifier"]),
            redirect_uri=f"{settings.public_base_url}{GOOGLE_CALLBACK_PATH}",
        )
        user = await google_oauth.sign_in(session, profile)
        tokens = await sessions.start_session(
            session, settings, user, user_agent=request.headers.get("user-agent")
        )
        await session.commit()
    except AppError as exc:
        await session.rollback()
        logger.info("auth.google_sign_in_failed", reason=exc.detail)
        return _login_error_redirect(settings, "google_failed")

    # The frontend decides where to go next (onboarding or the dashboard).
    response = RedirectResponse(
        f"{settings.public_base_url}/app", status_code=status.HTTP_303_SEE_OTHER
    )
    _apply(response, settings, tokens)
    response.delete_cookie(OAUTH_STATE_COOKIE, path=GOOGLE_CALLBACK_PATH)
    return response
