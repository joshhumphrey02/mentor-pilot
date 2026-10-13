import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.school import School


class UserRole(StrEnum):
    STUDENT = "student"
    MENTOR = "mentor"
    SCHOOL_ADMIN = "school_admin"
    ADMIN = "admin"


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    # Always stored lowercased; see services.auth.normalise_email.
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    # Null for accounts that only sign in with Google.
    password_hash: Mapped[str | None] = mapped_column(String(255))
    google_sub: Mapped[str | None] = mapped_column(String(255), unique=True)

    full_name: Mapped[str] = mapped_column(String(120), default="")
    role: Mapped[str] = mapped_column(String(20), default=UserRole.STUDENT.value, index=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="en")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    privacy_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user", uselist=False, lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def is_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_onboarded(self) -> bool:
        return self.onboarded_at is not None

    @property
    def privacy_accepted(self) -> bool:
        return self.privacy_accepted_at is not None

    @property
    def has_password(self) -> bool:
        return self.password_hash is not None


class StudentProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """What the mentor needs to personalise guidance for a learner.

    `education_level` is separate from `grade` so university students can be
    added later without reshaping this table.
    """

    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="SET NULL"), index=True
    )
    education_level: Mapped[str] = mapped_column(String(30), default="high_school")
    grade: Mapped[str | None] = mapped_column(String(20))
    province: Mapped[str | None] = mapped_column(String(60))
    interests: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'"))
    learning_style: Mapped[str | None] = mapped_column(String(30))

    date_of_birth: Mapped[date | None] = mapped_column(Date)
    # POPIA: a competent person must consent to processing a child's data.
    guardian_consent: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    guardian_email: Mapped[str | None] = mapped_column(String(320))
    guardian_consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="student_profile")
    school: Mapped[School | None] = relationship(lazy="selectin")


class AuditLog(UUIDPrimaryKeyMixin, Base):
    """Security-relevant events: logins, password changes, exports, deletions."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_user_id_created_at", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(60), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
