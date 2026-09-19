"""Popularity score persistence model."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class PopularityScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deterministic, versioned popularity score snapshot for a source."""

    __tablename__ = "popularity_scores"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    algorithm_version: Mapped[str] = mapped_column(String(50), default="popularity_v1", nullable=False)
    input_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    component_scores: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    final_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    missing_inputs: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    # Relationships
    source = relationship("Source", back_populates="popularity_scores")
    project = relationship("Project")
