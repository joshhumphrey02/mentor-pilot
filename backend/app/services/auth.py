"""Registration, email verification, login and password reset."""

import uuid
from datetime import timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, NotAuthenticatedError
from app.core.security import hash_password, hash_token, new_token, verify_password
from app.core.time import utcnow
from app.models import EmailToken, EmailTokenPurpose, User, UserRole
from app.services import audit, email, sessions
from app.services.email import Mailer

logger = structlog.get_logger(__name__)


def normalise_email(address: str) -> str:
    return address.strip().lower()


async def get_user_by_email(session: AsyncSession, address: str) -> User | None:
    user: User | None = await session.scalar(
        select(User).where(User.email == normalise_email(address), User.deleted_at.is_(None))
    )
    return user


def _invalid_token() -> AppError:
    return AppError(
        "This link is invalid or has expired. Please request a new one.", code="invalid_token"
    )


async def _issue_email_token(
    session: AsyncSession, user: User, purpose: EmailTokenPurpose, ttl: timedelta
) -> str:
    """Creates a token, retiring any earlier unused ones for the same purpose."""
    now = utcnow()
    await session.execute(
        update(EmailToken)
        .where(
            EmailToken.user_id == user.id,
            EmailToken.purpose == purpose.value,
            EmailToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw = new_token()
    session.add(
        EmailToken(
            user_id=user.id,
            purpose=purpose.value,
            token_hash=hash_token(raw),
            expires_at=now + ttl,
        )
    )
    return raw


async def _consume_email_token(session: AsyncSession, raw: str, purpose: EmailTokenPurpose) -> User:
    token = await session.scalar(
        select(EmailToken)
        .where(EmailToken.token_hash == hash_token(raw), EmailToken.purpose == purpose.value)
        .with_for_update()
    )
    if token is None or token.used_at is not None or token.expires_at <= utcnow():
        raise _invalid_token()
    user = await session.get(User, token.user_id)
    if user is None or user.deleted_at is not None or not user.is_active:
        raise _invalid_token()
    token.used_at = utcnow()
    return user


async def _send_verification(
    session: AsyncSession, settings: Settings, mailer: Mailer, user: User
) -> None:
    raw = await _issue_email_token(
        session,
        user,
        EmailTokenPurpose.VERIFY_EMAIL,
        timedelta(hours=settings.email_verify_ttl_hours),
    )
    link = f"{settings.public_base_url}/verify-email?token={raw}"
    mailer.send_later(
        email.verification_email(user.email, user.full_name, link, settings.email_verify_ttl_hours)
    )


async def register(
    session: AsyncSession,
    settings: Settings,
    mailer: Mailer,
    *,
    email_address: str,
    password: str,
    full_name: str,
) -> None:
    """Creates an unverified account and emails a confirmation link.

    Returns nothing, and behaves the same whether or not the address is taken,
    so the endpoint cannot be used to discover who has an account.
    """
    address = normalise_email(email_address)
    # Hashed before the lookup so both branches take the same time.
    password_hash = await hash_password(password)

    existing = await get_user_by_email(session, address)
    if existing is not None:
        if existing.is_verified:
            mailer.send_later(
                email.account_exists_email(
                    existing.email, existing.full_name, f"{settings.public_base_url}/login"
                )
            )
        else:
            await _send_verification(session, settings, mailer, existing)
            await session.commit()
        return

    user = User(
        email=address,
        password_hash=password_hash,
        full_name=full_name,
        role=UserRole.STUDENT.value,
        privacy_accepted_at=utcnow(),
    )
    session.add(user)
    await session.flush()
    await _send_verification(session, settings, mailer, user)
    audit.record(session, "auth.registered", user_id=user.id, method="password")
    await session.commit()


async def resend_verification(
    session: AsyncSession, settings: Settings, mailer: Mailer, *, email_address: str
) -> None:
    user = await get_user_by_email(session, email_address)
    if user is None or user.is_verified or not user.is_active:
        return
    await _send_verification(session, settings, mailer, user)
    await session.commit()


async def verify_email(
    session: AsyncSession, settings: Settings, *, token: str, user_agent: str | None
) -> tuple[User, sessions.SessionTokens]:
    """Confirms the address and signs the user in, so they land straight in onboarding."""
    user = await _consume_email_token(session, token, EmailTokenPurpose.VERIFY_EMAIL)
    now = utcnow()
    if user.email_verified_at is None:
        user.email_verified_at = now
    user.last_login_at = now
    tokens = await sessions.start_session(session, settings, user, user_agent=user_agent)
    audit.record(session, "auth.email_verified", user_id=user.id)
    await session.commit()
    return user, tokens


async def login(
    session: AsyncSession,
    settings: Settings,
    *,
    email_address: str,
    password: str,
    user_agent: str | None,
) -> tuple[User, sessions.SessionTokens]:
    user = await get_user_by_email(session, email_address)
    now = utcnow()

    if user is not None and user.locked_until is not None and user.locked_until > now:
        minutes = max(1, round((user.locked_until - now).total_seconds() / 60))
        unit = "minute" if minutes == 1 else "minutes"
        raise AppError(
            f"Too many failed attempts. Try again in {minutes} {unit}.",
            code="account_locked",
            status_code=423,
        )

    password_ok = await verify_password(password, user.password_hash if user else None)
    if user is None or not password_ok or user.password_hash is None or not user.is_active:
        if user is not None:
            await _record_failed_login(session, settings, user)
        raise NotAuthenticatedError("Incorrect email or password.", code="invalid_credentials")

    if not user.is_verified:
        raise AppError(
            "Please confirm your email address first. Check your inbox for the link.",
            code="email_not_verified",
            status_code=403,
        )

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = await sessions.start_session(session, settings, user, user_agent=user_agent)
    audit.record(session, "auth.login", user_id=user.id, method="password")
    await session.commit()
    return user, tokens


async def _record_failed_login(session: AsyncSession, settings: Settings, user: User) -> None:
    user.failed_login_count += 1
    if user.failed_login_count >= settings.max_failed_logins:
        user.locked_until = utcnow() + timedelta(minutes=settings.lockout_minutes)
        user.failed_login_count = 0
        audit.record(session, "auth.account_locked", user_id=user.id)
        logger.warning("auth.account_locked", user_id=str(user.id))
    await session.commit()


async def forgot_password(
    session: AsyncSession, settings: Settings, mailer: Mailer, *, email_address: str
) -> None:
    user = await get_user_by_email(session, email_address)
    if user is None or not user.is_active:
        return
    raw = await _issue_email_token(
        session,
        user,
        EmailTokenPurpose.RESET_PASSWORD,
        timedelta(minutes=settings.password_reset_ttl_minutes),
    )
    link = f"{settings.public_base_url}/reset-password?token={raw}"
    mailer.send_later(
        email.password_reset_email(
            user.email, user.full_name, link, settings.password_reset_ttl_minutes
        )
    )
    audit.record(session, "auth.password_reset_requested", user_id=user.id)
    await session.commit()


async def reset_password(session: AsyncSession, *, token: str, password: str) -> None:
    user = await _consume_email_token(session, token, EmailTokenPurpose.RESET_PASSWORD)
    user.password_hash = await hash_password(password)
    user.failed_login_count = 0
    user.locked_until = None
    # Using the emailed link proves control of the inbox.
    if user.email_verified_at is None:
        user.email_verified_at = utcnow()
    # Whoever knew the old password, or held a stolen session, is signed out.
    await sessions.revoke_all_for_user(session, user.id)
    audit.record(session, "auth.password_reset", user_id=user.id)
    await session.commit()


async def get_active_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    user = await session.get(User, user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        return None
    return user
