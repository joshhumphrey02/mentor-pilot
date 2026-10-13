import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def record(
    session: AsyncSession, action: str, *, user_id: uuid.UUID | None = None, **details: Any
) -> None:
    """Adds an audit entry to the current transaction (the caller commits)."""
    session.add(AuditLog(user_id=user_id, action=action, details=details))
