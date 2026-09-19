"""Source model representing raw discovered podcast or video."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import LicenseType, RightsStatus, SourceClass, WorkflowState


class Source(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """External source media record."""

    __tablename__ = "sources"

    channel_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("channels.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    platform: Mapped[str] = mapped_column(String(50), default="youtube", nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    views: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, index=True)
    likes: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    comments: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    workflow_state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState),
        default=WorkflowState.DISCOVERED,
        nullable=False,
        index=True,
    )
    source_class: Mapped[SourceClass] = mapped_column(
        Enum(SourceClass),
        default=SourceClass.UNKNOWN,
        nullable=False,
    )
    license_type: Mapped[LicenseType] = mapped_column(
        Enum(LicenseType),
        default=LicenseType.UNKNOWN,
        nullable=False,
    )
    rights_status: Mapped[RightsStatus] = mapped_column(
        Enum(RightsStatus),
        default=RightsStatus.REVIEW_REQUIRED,
        nullable=False,
        index=True,
    )

    # Relationships
    rights_record = relationship("RightsRecord", back_populates="source", uselist=False, cascade="all, delete-orphan")
    transcripts = relationship("Transcript", back_populates="source", cascade="all, delete-orphan")
    clip_candidates = relationship("ClipCandidate", back_populates="source", cascade="all, delete-orphan")
    trend_scores = relationship("TrendScore", back_populates="source", cascade="all, delete-orphan")
    popularity_scores = relationship("PopularityScore", back_populates="source", cascade="all, delete-orphan")
