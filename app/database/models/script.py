"""Script model for original story formulation."""

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Script(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Original transformed script with hook, context, analysis, and payoff."""

    __tablename__ = "scripts"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clip_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("clip_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    analysis: Mapped[str] = mapped_column(Text, nullable=False)
    insight: Mapped[str] = mapped_column(Text, nullable=False)
    payoff: Mapped[str] = mapped_column(Text, nullable=False)
    cta: Mapped[str] = mapped_column(Text, nullable=False)
    full_script: Mapped[str] = mapped_column(Text, nullable=False)

    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    project = relationship("Project", back_populates="scripts")
