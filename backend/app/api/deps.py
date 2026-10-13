"""Shared FastAPI dependencies: the database session, settings, the signed-in user."""

from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import BackgroundTasks, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.cookies import ACCESS_COOKIE
from app.core.errors import NotAuthenticatedError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User, UserRole
from app.services.auth import get_active_user
from app.services.email import Mailer

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_mailer(request: Request, background: BackgroundTasks) -> Mailer:
    return Mailer(request.app.state.email_sender, background)


MailerDep = Annotated[Mailer, Depends(get_mailer)]


async def get_current_user(request: Request, session: SessionDep, settings: SettingsDep) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    user_id = decode_access_token(settings, token) if token else None
    if user_id is None:
        raise NotAuthenticatedError("Please log in to continue.")
    # Loaded on every request (not trusted from the JWT) so that deactivating
    # an account or changing a role takes effect immediately.
    user = await get_active_user(session, user_id)
    if user is None:
        raise NotAuthenticatedError("Please log in to continue.")
    structlog.contextvars.bind_contextvars(user_id=str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], Awaitable[User]]:
    """Dependency factory: `Depends(require_roles(UserRole.ADMIN))`."""
    allowed = {role.value for role in roles}

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError("You don't have access to this.")
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
