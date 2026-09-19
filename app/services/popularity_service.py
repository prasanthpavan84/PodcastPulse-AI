"""Popularity service computing and persisting versioned popularity scores."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.database.models.popularity import PopularityScore
from app.domain.popularity.scorer import PopularityScorer
from app.repositories.audit_repository import AuditRepository
from app.repositories.popularity_repository import PopularityRepository
from app.repositories.source_repository import SourceRepository

logger = get_logger("popularity_service")


class PopularityService:
    """Computes deterministic popularity scores and records auditable score snapshots.

    SAFETY INVARIANT:
    Popularity scores are advisory only. They NEVER mutate rights status, NEVER mutate
    workflow state, and NEVER authorize media processing or publishing.
    """

    @staticmethod
    def calculate_and_record(
        session: Session,
        source_id: str,
        project_id: Optional[str] = None,
        channel_signals: Optional[Dict[str, Any]] = None,
        reference_time: Optional[datetime] = None,
        request_id: Optional[str] = None,
    ) -> PopularityScore:
        """Calculate popularity_v1 score for a source and persist snapshot.

        Never fabricates missing metadata: missing values are recorded and omitted from scoring.
        """
        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)

        # Execute pure domain scoring
        result = PopularityScorer.calculate_score(
            published_at=source.published_at,
            views=source.views,
            likes=source.likes,
            comments=source.comments,
            duration_seconds=source.duration_seconds,
            channel_signals=channel_signals,
            reference_time=reference_time,
        )

        # Persist record
        score_record = PopularityScore(
            source_id=source.id,
            project_id=project_id,
            algorithm_version=result.algorithm_version,
            input_snapshot=result.input_snapshot,
            component_scores=result.component_scores,
            final_score=result.final_score,
            rationale=result.rationale,
            missing_inputs=result.missing_inputs,
            scored_at=result.scored_at,
        )
        PopularityRepository.save(session, score_record)

        # Record audit event
        AuditRepository.record_event(
            session=session,
            actor="popularity_engine",
            action="POPULARITY_SCORE_CALCULATED",
            entity_type="Source",
            entity_id=source.id,
            project_id=project_id,
            request_id=request_id,
            payload={
                "algorithm_version": result.algorithm_version,
                "final_score": result.final_score,
                "component_scores": result.component_scores,
                "missing_inputs": result.missing_inputs,
                "rationale": result.rationale,
            },
        )

        logger.info(
            "popularity_score_calculated",
            source_id=source.id,
            final_score=result.final_score,
            version=result.algorithm_version,
        )
        return score_record

    @staticmethod
    def get_latest_score(session: Session, source_id: str) -> Optional[PopularityScore]:
        """Fetch latest popularity score for a source."""
        return PopularityRepository.get_latest_by_source_id(session, source_id)

    @staticmethod
    def list_history(session: Session, source_id: str) -> List[PopularityScore]:
        """List historical popularity score records for a source."""
        return PopularityRepository.list_by_source_id(session, source_id)
