"""Publishing job and published video models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PublishingJob(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Publishing execution queue record."""

    __tablename__ = "publishing_jobs"

    render_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("renders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(50), default="youtube", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False, index=True)
    privacy_status: Mapped[str] = mapped_column(String(50), default="private", nullable=False)
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    render = relationship("Render", back_populates="publishing_jobs")
    published_videos = relationship("PublishedVideo", back_populates="publishing_job")


class PublishedVideo(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Record of an active published video."""

    __tablename__ = "published_videos"

    publishing_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("publishing_jobs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(50), default="youtube", nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    publishing_job = relationship("PublishingJob", back_populates="published_videos")
    analytics = relationship("AnalyticsRecord", back_populates="published_video", cascade="all, delete-orphan")
