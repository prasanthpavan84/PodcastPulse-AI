"""Explicit repository for Channel entities."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models.channel import Channel


class ChannelRepository:
    """Persistence operations for external content channels."""

    @staticmethod
    def get_by_id(session: Session, channel_uuid: str) -> Optional[Channel]:
        """Fetch a channel by internal primary UUID."""
        stmt = select(Channel).where(Channel.id == channel_uuid)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_channel_id(session: Session, external_channel_id: str, platform: str = "youtube") -> Optional[Channel]:
        """Fetch a channel by external platform ID."""
        stmt = select(Channel).where(
            Channel.channel_id == external_channel_id,
            Channel.platform == platform,
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def save(session: Session, channel: Channel) -> Channel:
        """Insert or update a channel record."""
        session.add(channel)
        session.flush()
        return channel

    @classmethod
    def get_or_create(
        cls,
        session: Session,
        external_channel_id: str,
        channel_name: str,
        url: str,
        platform: str = "youtube",
        thumbnail_url: Optional[str] = None,
    ) -> Channel:
        """Fetch existing channel or create a new one using savepoints for transaction safety."""
        # 1. Pre-check
        existing = cls.get_by_channel_id(session, external_channel_id, platform=platform)
        if existing:
            if thumbnail_url and not existing.thumbnail_url:
                existing.thumbnail_url = thumbnail_url
                session.flush()
            return existing

        # 2. Savepoint-protected creation
        channel = Channel(
            platform=platform,
            channel_id=external_channel_id,
            channel_name=channel_name or "Unknown Channel",
            url=url,
            thumbnail_url=thumbnail_url,
        )
        try:
            with session.begin_nested():
                session.add(channel)
                session.flush()
            return channel
        except IntegrityError:
            # Concurrent insert resolved by lookup
            existing = cls.get_by_channel_id(session, external_channel_id, platform=platform)
            if existing:
                return existing
            raise
