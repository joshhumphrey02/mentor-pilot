"""Importing this package registers every model on `Base.metadata`."""

from app.models.ai_usage import AIUsage
from app.models.pathway import ProjectStage, StageDefinition, StageStatus
from app.models.project import (
    Conversation,
    Message,
    MessageRole,
    MessageStatus,
    ModerationFlag,
    Project,
    ProjectStatus,
)
from app.models.school import School
from app.models.token import EmailToken, EmailTokenPurpose, RefreshToken
from app.models.user import AuditLog, StudentProfile, User, UserRole

__all__ = [
    "AIUsage",
    "AuditLog",
    "Conversation",
    "EmailToken",
    "EmailTokenPurpose",
    "Message",
    "MessageRole",
    "MessageStatus",
    "ModerationFlag",
    "Project",
    "ProjectStage",
    "ProjectStatus",
    "RefreshToken",
    "School",
    "StageDefinition",
    "StageStatus",
    "StudentProfile",
    "User",
    "UserRole",
]
