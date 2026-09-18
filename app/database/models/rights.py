"""Rights record model storing evidence and verification decisions."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import LicenseType, RightsStatus, SourceClass


class RightsRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Immutable/auditable record of copyright and reuse permissions."""

    __tablename__ = "rights_records"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="CASCADE"),
        unique=True,
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
    commercial_use: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    modification_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evidence_reference: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    evidence_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    evidence_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewer: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    decision: Mapped[RightsStatus] = mapped_column(
        Enum(RightsStatus),
        default=RightsStatus.REVIEW_REQUIRED,
        nullable=False,
    )
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ruleset_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    source = relationship("Source", back_populates="rights_record")
