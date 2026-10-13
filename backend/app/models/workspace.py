import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LogbookEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A learner's own dated note. Expo judges read logbooks, so entries keep
    their original timestamp and the stage they were written in."""

    __tablename__ = "logbook_entries"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    stage_key: Mapped[str] = mapped_column(String(40), default="")


class PinnedItem(UUIDPrimaryKeyMixin, Base):
    """A block the learner saved from a conversation: a diagram, circuit, materials list."""

    __tablename__ = "pinned_items"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    # Kept if the message is later regenerated away: the pin holds its own copy.
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(160), default="")
    block: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class ExperimentDataset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A table of the learner's own measurements."""

    __tablename__ = "experiment_datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(160), default="")
    columns: Mapped[list[str]] = mapped_column(JSONB, default=list)
    # Rows of cell text, exactly as typed. Numbers are parsed when charting.
    rows: Mapped[list[list[str]]] = mapped_column(JSONB, default=list)


class Attachment(UUIDPrimaryKeyMixin, Base):
    """An uploaded file (a photo of a sketch, circuit or setup)."""

    __tablename__ = "attachments"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(60))
    size: Mapped[int] = mapped_column(Integer)
    # Where the bytes are, in whichever storage backend is configured.
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
