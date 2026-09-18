"""Render model for finalized vertical video renders."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Render(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Rendered vertical video output."""

    __tablename__ = "renders"

    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    caption_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    resolution: Mapped[str] = mapped_column(String(50), default="1080x1920", nullable=False)
    fps: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)

    # Relationships
    project = relationship("Project", back_populates="renders")
    quality_checks = relationship("QualityCheck", back_populates="render", cascade="all, delete-orphan")
    publishing_jobs = relationship("PublishingJob", back_populates="render")
