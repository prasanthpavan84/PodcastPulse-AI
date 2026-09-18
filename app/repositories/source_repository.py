"""Explicit repository for Source entities."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.source import Source
from app.domain.enums import WorkflowState


class SourceRepository:
    """Persistence operations for Source media records."""

    @staticmethod
    def get_by_id(session: Session, source_id: str) -> Optional[Source]:
        """Fetch a source by its primary UUID."""
        stmt = select(Source).where(Source.id == source_id, Source.deleted_at.is_(None))
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_external_id(session: Session, external_id: str, platform: str = "youtube") -> Optional[Source]:
        """Fetch a source by its external platform ID."""
        stmt = select(Source).where(
            Source.external_id == external_id,
            Source.platform == platform,
            Source.deleted_at.is_(None),
        )
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_sources(
        session: Session,
        workflow_state: Optional[WorkflowState] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Source]:
        """List active sources optionally filtered by workflow state."""
        stmt = select(Source).where(Source.deleted_at.is_(None))
        if workflow_state:
            stmt = stmt.where(Source.workflow_state == workflow_state)
        stmt = stmt.order_by(Source.published_at.desc()).offset(offset).limit(limit)
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def save(session: Session, source: Source) -> Source:
        """Insert or update a source record."""
        session.add(source)
        session.flush()
        return source
