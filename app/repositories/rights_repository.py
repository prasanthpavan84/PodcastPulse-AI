"""Explicit repository for RightsRecord entities."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.rights import RightsRecord


class RightsRepository:
    """Persistence operations for Rights records."""

    @staticmethod
    def get_by_source_id(session: Session, source_id: str) -> Optional[RightsRecord]:
        """Fetch rights clearance record for a source."""
        stmt = select(RightsRecord).where(RightsRecord.source_id == source_id)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def save(session: Session, rights_record: RightsRecord) -> RightsRecord:
        """Insert or update a rights record."""
        session.add(rights_record)
        session.flush()
        return rights_record
