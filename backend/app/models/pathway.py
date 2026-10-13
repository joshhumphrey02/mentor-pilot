import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StageDefinition(TimestampMixin, Base):
    """One stage of the pathway. Editable data, not code (see pathway/stages.yaml)."""

    __tablename__ = "stage_definitions"

    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    position: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(80))
    goal: Mapped[str] = mapped_column(Text)
    # [{"key": "...", "label": "..."}]
    deliverables: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    exit_criteria: Mapped[list[str]] = mapped_column(JSONB)
    # Added to the mentor's system prompt while a project is in this stage.
    instructions: Mapped[str] = mapped_column(Text, default="")
    # Where a human mentor is offered.
    handoff: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    version: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))


class StageStatus(StrEnum):
    LOCKED = "locked"
    ACTIVE = "active"
    COMPLETED = "completed"


class ProjectStage(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A project's progress through one stage, including its checklist."""

    __tablename__ = "project_stages"
    __table_args__ = (UniqueConstraint("project_id", "stage_key"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    stage_key: Mapped[str] = mapped_column(ForeignKey("stage_definitions.key", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default=StageStatus.LOCKED.value)
    # {deliverable_key: {"done": bool, "note": str, "by": "mentor"|"learner", "at": iso}}
    checklist: Mapped[dict[str, dict[str, Any]]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
