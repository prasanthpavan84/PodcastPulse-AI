"""Analytics record model."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AnalyticsRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Snapshot of published video engagement and retention statistics."""

    __tablename__ = "analytics"

    published_video_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("published_videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    likes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    shares: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    subscribers_gained: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_view_duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    retention_rate: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Relationships
    published_video = relationship("PublishedVideo", back_populates="analytics")
