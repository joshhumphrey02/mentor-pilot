"""Login sessions: an access JWT plus a rotating, hashed refresh token."""

import uuid
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotAuthenticatedError
from app.core.security import create_access_token, hash_token, new_csrf_token, new_token
from app.core.time import utcnow
from app.models import RefreshToken, User
from app.services import audit

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class SessionTokens:
    access_token: str
    refresh_token: str
    csrf_token: str


class RefreshRaceError(AppError):
    """The token was rotated a moment ago, almost certainly by another tab."""

    status_code = 409
    code = "refresh_in_progress"


def _invalid_session() -> NotAuthenticatedError:
    return NotAuthenticatedError(
        "Your session has ended. Please log in again.", code="invalid_session"
    )


def _add_refresh_token(
    session: AsyncSession,
    settings: Settings,
    *,
    user_id: uuid.UUID,
    family_id: uuid.UUID,
    user_agent: str | None,
) -> str:
    raw = new_token()
    session.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id,
            token_hash=hash_token(raw),
            expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
            user_agent=(user_agent or "")[:255] or None,
        )
    )
    return raw


def _tokens_for(settings: Settings, user: User, refresh_token: str) -> SessionTokens:
    return SessionTokens(
        access_token=create_access_token(settings, user_id=user.id, role=user.role),
        refresh_token=refresh_token,
        csrf_token=new_csrf_token(settings),
    )


async def start_session(
    session: AsyncSession, settings: Settings, user: User, *, user_agent: str | None
) -> SessionTokens:
    """Begins a new token family. The caller commits."""
    refresh = _add_refresh_token(
        session, settings, user_id=user.id, family_id=uuid.uuid4(), user_agent=user_agent
    )
    return _tokens_for(settings, user, refresh)


async def rotate_session(
    session: AsyncSession, settings: Settings, raw_refresh_token: str, *, user_agent: str | None
) -> tuple[User, SessionTokens]:
    now = utcnow()
    # Lock the row so two concurrent refreshes cannot both see it as unused.
    token = await session.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_token(raw_refresh_token))
        .with_for_update()
    )
    if token is None or token.revoked_at is not None or token.expires_at <= now:
        raise _invalid_session()

    if token.used_at is not None:
        if now - token.used_at <= timedelta(seconds=settings.refresh_reuse_grace_seconds):
            # The winning request already set fresh cookies in this browser.
            raise RefreshRaceError("Session refresh already in progress. Please retry.")
        # A token that was rotated a while ago is being replayed: assume it was
        # stolen and end every session descended from that login.
        await revoke_family(session, token.family_id)
        audit.record(session, "auth.refresh_reuse_detected", user_id=token.user_id)
        await session.commit()
        logger.warning("auth.refresh_reuse_detected", user_id=str(token.user_id))
        raise _invalid_session()

    user = await session.get(User, token.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise _invalid_session()

    token.used_at = now
    refresh = _add_refresh_token(
        session, settings, user_id=user.id, family_id=token.family_id, user_agent=user_agent
    )
    await session.commit()
    return user, _tokens_for(settings, user, refresh)


async def revoke_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


async def end_session(session: AsyncSession, raw_refresh_token: str | None) -> None:
    """Logout: revokes the family this browser's refresh token belongs to."""
    if not raw_refresh_token:
        return
    token = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh_token))
    )
    if token is not None:
        await revoke_family(session, token.family_id)
        audit.record(session, "auth.logout", user_id=token.user_id)
        await session.commit()
