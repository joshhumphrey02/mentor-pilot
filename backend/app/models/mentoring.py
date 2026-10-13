import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import text as sql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class MentorProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "mentor_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    organisation: Mapped[str] = mapped_column(String(160), default="")
    bio: Mapped[str] = mapped_column(Text, default="")
    # Help types this mentor can give (see HELP_TYPES).
    expertise: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Provinces they can serve.
    regions: Mapped[list[str]] = mapped_column(JSONB, default=list)
    availability: Mapped[str] = mapped_column(String(200), default="")
    offers: Mapped[str] = mapped_column(Text, default="")
    # Mentors work with minors, so an admin vets each one before they can see
    # or accept any learner's request.
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, server_default=sql("false"))


class RequestStatus(StrEnum):
    PENDING = "pending"
    MATCHED = "matched"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MentorRequest(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A learner asking for hands-on help from a human mentor."""

    __tablename__ = "mentor_requests"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    learner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    mentor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default=RequestStatus.PENDING.value, index=True)
    stage_key: Mapped[str] = mapped_column(String(40), default="")
    help_types: Mapped[list[str]] = mapped_column(JSONB, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    province: Mapped[str] = mapped_column(String(60), default="", index=True)
    school_name: Mapped[str] = mapped_column(String(160), default="")
    # What the project looked like when help was asked for, so the mentor has
    # context without being given access to the learner's conversations.
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class MentorMessage(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mentor_messages"

    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("mentor_requests.id", ondelete="CASCADE"), index=True
    )
    sender_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql("now()"), index=True
    )


class CreditLedger(UUIDPrimaryKeyMixin, Base):
    """Credits bought or granted, per learner or per school. Payments are not
    wired up yet; this is the record they will write to."""

    __tablename__ = "credit_ledger"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), index=True
    )
    # Positive for a grant or purchase, negative for a correction.
    delta: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=sql("now()")
    )


class ExpoEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """An upcoming science expo, shown on learners' dashboards. Managed by admins."""

    __tablename__ = "expo_events"

    name: Mapped[str] = mapped_column(String(160))
    starts_on: Mapped[date] = mapped_column(Date, index=True)
    location: Mapped[str] = mapped_column(String(160), default="")
    province: Mapped[str] = mapped_column(String(60), default="")
    url: Mapped[str] = mapped_column(String(300), default="")
