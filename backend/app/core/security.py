"""Password hashing, access JWTs, opaque tokens and CSRF tokens."""

import hashlib
import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Any

import jwt
from anyio import to_thread
from pwdlib import PasswordHash

from app.core.config import Settings
from app.core.time import utcnow

JWT_ALGORITHM = "HS256"

_password_hash = PasswordHash.recommended()  # argon2id

# Verified against when the account does not exist, so a login attempt costs
# the same time either way and response timing cannot reveal who has an account.
_DUMMY_HASH = _password_hash.hash("mentor-pilot-timing-equaliser")


async def hash_password(password: str) -> str:
    # argon2 is deliberately slow; keep it off the event loop.
    return await to_thread.run_sync(_password_hash.hash, password)


async def verify_password(password: str, password_hash: str | None) -> bool:
    return await to_thread.run_sync(_password_hash.verify, password, password_hash or _DUMMY_HASH)


def new_token() -> str:
    """A URL-safe random token with 256 bits of entropy."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Tokens are stored hashed, so a database leak does not leak live sessions.

    A plain SHA-256 is enough here (unlike for passwords) because the input is
    already high-entropy random data and cannot be brute-forced.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(settings: Settings, *, user_id: uuid.UUID, role: str) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(settings: Settings, token: str) -> uuid.UUID | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "type"]},
        )
        if payload["type"] != "access":
            return None
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError):
        return None


def create_signed_state(settings: Settings, data: dict[str, Any], *, ttl_seconds: int) -> str:
    """A short-lived signed blob, used to carry OAuth state in a cookie."""
    payload = {**data, "type": "state", "exp": utcnow() + timedelta(seconds=ttl_seconds)}
    return jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def read_signed_state(settings: Settings, token: str) -> dict[str, Any] | None:
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "type"]},
        )
    except jwt.PyJWTError:
        return None
    return payload if payload.get("type") == "state" else None


def _csrf_signature(settings: Settings, nonce: str) -> str:
    key = settings.secret_key.get_secret_value().encode()
    return hmac.new(key, f"csrf:{nonce}".encode(), hashlib.sha256).hexdigest()


def new_csrf_token(settings: Settings) -> str:
    """A signed double-submit token.

    Signing means an attacker who can plant a cookie (for example from a
    sibling subdomain) still cannot forge a token the server will accept.
    """
    nonce = secrets.token_urlsafe(24)
    return f"{nonce}.{_csrf_signature(settings, nonce)}"


def is_valid_csrf_token(settings: Settings, token: str) -> bool:
    nonce, _, signature = token.partition(".")
    if not nonce or not signature:
        return False
    return hmac.compare_digest(signature, _csrf_signature(settings, nonce))
