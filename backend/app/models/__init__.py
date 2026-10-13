"""Importing this package registers every model on `Base.metadata`."""

from app.models.school import School
from app.models.token import EmailToken, EmailTokenPurpose, RefreshToken
from app.models.user import AuditLog, StudentProfile, User, UserRole

__all__ = [
    "AuditLog",
    "EmailToken",
    "EmailTokenPurpose",
    "RefreshToken",
    "School",
    "StudentProfile",
    "User",
    "UserRole",
]
