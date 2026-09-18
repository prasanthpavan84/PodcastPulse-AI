"""Trend and popularity scoring model for discovered sources."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utc_now


class TrendScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Deterministic virality & opportunity signal snapshot for a source."""

    __tablename__ = "trend_scores"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    view_velocity: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(50), default="trend_v1", nullable=False)
    signal_snapshot: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    # Relationships
    source = relationship("Source", back_populates="trend_scores")
