"""Channel model."""

from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Channel(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """External content channel (e.g. YouTube channel)."""

    __tablename__ = "channels"

    platform: Mapped[str] = mapped_column(String(50), default="youtube", nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    channel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
