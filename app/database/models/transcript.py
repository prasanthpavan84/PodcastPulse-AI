"""Transcript and TranscriptSegment models."""

from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Transcript(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Full audio transcript of a source video."""

    __tablename__ = "transcripts"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    language: Mapped[str] = mapped_column(String(20), default="en", nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="whisper", nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), default="base", nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    file_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Relationships
    source = relationship("Source", back_populates="transcripts")
    segments = relationship("TranscriptSegment", back_populates="transcript", cascade="all, delete-orphan")


class TranscriptSegment(Base, UUIDPrimaryKeyMixin):
    """Timestamped segment within a transcript."""

    __tablename__ = "transcript_segments"

    transcript_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("transcripts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    speaker: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    transcript = relationship("Transcript", back_populates="segments")
