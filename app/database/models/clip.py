"""Clip candidate and scoring models."""

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ClipCandidate(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Semantic clip candidate extracted from source transcript."""

    __tablename__ = "clip_candidates"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    hook: Mapped[str] = mapped_column(Text, nullable=False)
    payoff: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="CANDIDATE", nullable=False)

    # Relationships
    source = relationship("Source", back_populates="clip_candidates")
    scores = relationship("ClipScore", back_populates="clip", uselist=False, cascade="all, delete-orphan")


class ClipScore(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Multi-dimensional scoring for clip virality, meaning, and retention potential."""

    __tablename__ = "clip_scores"

    clip_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clip_candidates.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    hook_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    meaning_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    standalone_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    novelty_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    emotion_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    usefulness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    retention_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visual_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    final_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    algorithm_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)

    # Relationships
    clip = relationship("ClipCandidate", back_populates="scores")
