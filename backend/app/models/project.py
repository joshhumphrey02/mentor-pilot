import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

FIRST_STAGE = "problem_discovery"


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Project(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_owner_id_last_activity_at", "owner_id", "last_activity_at"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160), default="")
    # The idea the learner chose, once they have (set by the select_idea tool).
    idea: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    current_stage: Mapped[str] = mapped_column(String(40), default=FIRST_STAGE)
    # A rolling summary of the conversation so far, refreshed by the fast model,
    # so the mentor keeps context without resending the whole history.
    memory: Mapped[str] = mapped_column(Text, default="", server_default="")
    # How many messages the summary already covers, so it is refreshed every
    # few turns rather than on every one.
    memory_message_count: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.ACTIVE.value)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Conversation(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_project_id_last_message_at", "project_id", "last_message_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    # Empty until the fast model names it after the first exchange.
    title: Mapped[str] = mapped_column(String(160), default="", server_default="")
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    # The assistant is still writing. Set when the turn starts so that a
    # client which loses its connection can find the message and wait for it.
    STREAMING = "streaming"
    COMPLETE = "complete"
    ERROR = "error"
    # Withheld by moderation: the content is not shown or sent to the model.
    BLOCKED = "blocked"


class Message(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_id_seq", "conversation_id", "seq"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    # A strictly increasing number, so ordering never depends on clock precision.
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default=MessageStatus.COMPLETE.value)

    # What the UI renders: an ordered list of typed blocks (see app.ai.blocks).
    blocks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default=text("'[]'")
    )
    # What the model saw or wrote, verbatim. Used to rebuild the history for
    # the next turn, and for search.
    raw: Mapped[str] = mapped_column(Text, default="", server_default="")

    provider: Mapped[str | None] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(100))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    # Thumbs up (1) or down (-1) from the learner.
    feedback: Mapped[int | None] = mapped_column(SmallInteger)


class ModerationFlag(UUIDPrimaryKeyMixin, Base):
    """Content the safety layer stopped, kept for an admin to review."""

    __tablename__ = "moderation_flags"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL")
    )
    # "input": the learner's message. "output": the mentor's reply.
    direction: Mapped[str] = mapped_column(String(10))
    categories: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default=text("'[]'"))
    # False when the message was blocked because the check itself failed.
    checked: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )
