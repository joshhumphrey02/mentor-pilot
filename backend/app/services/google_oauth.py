"""Sign in with Google (OAuth 2.0 authorization code flow with PKCE)."""

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode

import httpx
from authlib.common.security import generate_token
from authlib.oauth2.rfc7636 import create_s256_code_challenge
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError
from app.core.time import utcnow
from app.models import User, UserRole
from app.services import audit
from app.services.auth import get_user_by_email, normalise_email

AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105  (an endpoint, not a secret)
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPE = "openid email profile"


@dataclass(frozen=True)
class GoogleProfile:
    sub: str
    email: str
    email_verified: bool
    name: str


@dataclass(frozen=True)
class AuthorizationRequest:
    url: str
    state: str
    code_verifier: str


class GoogleOAuthError(AppError):
    code = "google_sign_in_failed"


class GoogleOAuthClient(Protocol):
    def authorization_request(self, redirect_uri: str) -> AuthorizationRequest: ...

    async def fetch_profile(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> GoogleProfile: ...


class HttpxGoogleOAuthClient:
    def __init__(self, settings: Settings) -> None:
        self.client_id = settings.google_client_id or ""
        secret = settings.google_client_secret
        self.client_secret = secret.get_secret_value() if secret else ""

    def authorization_request(self, redirect_uri: str) -> AuthorizationRequest:
        state = generate_token(32)
        code_verifier = generate_token(64)
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": SCOPE,
                "state": state,
                "code_challenge": create_s256_code_challenge(code_verifier),
                "code_challenge_method": "S256",
                "prompt": "select_account",
            }
        )
        return AuthorizationRequest(f"{AUTHORIZE_URL}?{query}", state, code_verifier)

    async def fetch_profile(
        self, *, code: str, code_verifier: str, redirect_uri: str
    ) -> GoogleProfile:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                token_response = await client.post(
                    TOKEN_URL,
                    data={
                        "grant_type": "authorization_code",
                        "code": code,
                        "code_verifier": code_verifier,
                        "redirect_uri": redirect_uri,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    },
                )
                token_response.raise_for_status()
                # The access token came straight from Google over TLS, so the
                # userinfo it unlocks is trustworthy without verifying an ID token.
                userinfo = await client.get(
                    USERINFO_URL,
                    headers={"Authorization": f"Bearer {token_response.json()['access_token']}"},
                )
                userinfo.raise_for_status()
                data = userinfo.json()
            return GoogleProfile(
                sub=str(data["sub"]),
                email=str(data["email"]),
                email_verified=bool(data.get("email_verified", False)),
                name=str(data.get("name") or ""),
            )
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            raise GoogleOAuthError("We couldn't sign you in with Google.") from exc


async def sign_in(session: AsyncSession, profile: GoogleProfile) -> User:
    """Finds or creates the account for a Google profile. The caller commits."""
    if not profile.email_verified:
        raise GoogleOAuthError("Your Google account's email address is not verified.")

    now = utcnow()
    user: User | None = await session.scalar(select(User).where(User.google_sub == profile.sub))
    if user is None:
        # Google has verified this address, so it is safe to link it to an
        # existing password account with the same email.
        user = await get_user_by_email(session, profile.email)
        if user is not None:
            user.google_sub = profile.sub

    if user is None:
        user = User(
            email=normalise_email(profile.email),
            google_sub=profile.sub,
            full_name=profile.name[:120],
            role=UserRole.STUDENT.value,
            email_verified_at=now,
        )
        session.add(user)
        await session.flush()
        audit.record(session, "auth.registered", user_id=user.id, method="google")
    elif not user.is_active or user.deleted_at is not None:
        raise GoogleOAuthError("This account is no longer active.")

    if user.email_verified_at is None:
        user.email_verified_at = now
    user.last_login_at = now
    audit.record(session, "auth.login", user_id=user.id, method="google")
    return user
