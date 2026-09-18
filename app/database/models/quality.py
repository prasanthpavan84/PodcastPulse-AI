"""Quality check model."""

from typing import Any, Dict, Optional

from sqlalchemy import JSON, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class QualityCheck(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Automated quality assessment metrics for rendered video."""

    __tablename__ = "quality_checks"

    render_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("renders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audio_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    caption_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visual_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    content_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    rights_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overall_status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)
    issues: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    # Relationships
    render = relationship("Render", back_populates="quality_checks")
