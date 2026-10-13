import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class School(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "schools"
    __table_args__ = (
        # The same school typed with different capitalisation is one school.
        Index("uq_schools_name_province", func.lower(text("name")), "province", unique=True),
    )

    name: Mapped[str] = mapped_column(String(160))
    province: Mapped[str] = mapped_column(String(60), default="", server_default="")
    town: Mapped[str | None] = mapped_column(String(120))
    # Learners can add their own school; an admin confirms it later.
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    # Kept so learner-added schools can be traced when moderating them.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
