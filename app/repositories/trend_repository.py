"""Explicit repository for TrendScore entities."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.trend import TrendScore


class TrendRepository:
    """Persistence operations for source TrendScore records."""

    @staticmethod
    def get_by_id(session: Session, trend_id: str) -> Optional[TrendScore]:
        """Fetch a trend score record by primary UUID."""
        stmt = select(TrendScore).where(TrendScore.id == trend_id)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_latest_by_source_id(session: Session, source_id: str) -> Optional[TrendScore]:
        """Fetch the most recent trend score for a given source."""
        stmt = (
            select(TrendScore)
            .where(TrendScore.source_id == source_id)
            .order_by(TrendScore.calculated_at.desc())
            .limit(1)
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_source_id(session: Session, source_id: str) -> List[TrendScore]:
        """List all historical trend scores for a source."""
        stmt = select(TrendScore).where(TrendScore.source_id == source_id).order_by(TrendScore.calculated_at.desc())
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def save(session: Session, trend_score: TrendScore) -> TrendScore:
        """Insert or update a trend score record."""
        session.add(trend_score)
        session.flush()
        return trend_score
