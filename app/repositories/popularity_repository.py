"""Explicit repository for PopularityScore entities."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.popularity import PopularityScore


class PopularityRepository:
    """Persistence operations for PopularityScore records."""

    @staticmethod
    def save(session: Session, popularity_score: PopularityScore) -> PopularityScore:
        """Insert or update a popularity score record."""
        session.add(popularity_score)
        session.flush()
        return popularity_score

    @staticmethod
    def get_by_id(session: Session, score_id: str) -> Optional[PopularityScore]:
        """Fetch popularity score by primary key."""
        stmt = select(PopularityScore).where(PopularityScore.id == score_id)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_latest_by_source_id(session: Session, source_id: str) -> Optional[PopularityScore]:
        """Fetch the most recent popularity score for a given source."""
        stmt = (
            select(PopularityScore)
            .where(PopularityScore.source_id == source_id)
            .order_by(PopularityScore.scored_at.desc())
            .limit(1)
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_source_id(session: Session, source_id: str) -> List[PopularityScore]:
        """List all historical popularity scores for a given source in chronological order."""
        stmt = (
            select(PopularityScore)
            .where(PopularityScore.source_id == source_id)
            .order_by(PopularityScore.scored_at.asc())
        )
        return list(session.execute(stmt).scalars().all())
