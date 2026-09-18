"""Discovery orchestration service with multi-level deduplication, transaction safety, and trend intelligence."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.interfaces import YouTubeDiscovery
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.database.models.source import Source
from app.database.models.trend import TrendScore
from app.discovery.query_builder import DiscoveryQueryBuilder
from app.discovery.trend_scorer import TrendScorer
from app.domain.enums import JobStatus, JobType, LicenseType, RightsStatus, SourceClass, WorkflowState
from app.repositories.audit_repository import AuditRepository
from app.repositories.channel_repository import ChannelRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.trend_repository import TrendRepository
from app.services.job_service import JobService

logger = get_logger("discovery_service")


class DiscoveryService:
    """Orchestrates content discovery runs, deduplication, deterministic trend scoring, and job tracking."""

    @staticmethod
    def generate_idempotency_key(
        topics: List[str],
        keywords: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
        min_views: int = 10000,
        published_after_days: Optional[int] = 30,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        max_results: int = 25,
    ) -> str:
        """Derive a deterministic SHA-256 idempotency key from discovery parameters."""
        raw_key = (
            f"yt_discovery:{sorted(topics)}:{sorted(keywords or [])}:{sorted(channels or [])}:"
            f"{min_views}:{published_after_days}:{published_after}:{published_before}:{max_results}"
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    @classmethod
    def discover_youtube_candidates(
        cls,
        session: Session,
        adapter: YouTubeDiscovery,
        topics: List[str],
        keywords: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
        min_views: int = 10000,
        published_after_days: Optional[int] = 30,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        max_results: int = 25,
        max_queries: Optional[int] = None,
        idempotency_key: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute discovery workflow with strict idempotency, rights safety, and transaction isolation."""
        # 1. Validate query inputs up front
        DiscoveryQueryBuilder.build_queries(
            topics=topics,
            keywords=keywords,
            channels=channels,
            published_after_days=published_after_days,
            published_after=published_after,
            published_before=published_before,
            max_results=max_results,
            max_queries_per_run=max_queries or 5,
        )

        # 2. Derive or validate idempotency key
        idem_key = idempotency_key or cls.generate_idempotency_key(
            topics=topics,
            keywords=keywords,
            channels=channels,
            min_views=min_views,
            published_after_days=published_after_days,
            published_after=published_after,
            published_before=published_before,
            max_results=max_results,
        )

        # 3. Check / create execution Job
        job = JobService.get_or_create_job(
            session=session,
            job_type=JobType.DISCOVERY_JOB,
            idempotency_key=idem_key,
            metadata_json={
                "topics": topics,
                "keywords": keywords,
                "channels": channels,
                "min_views": min_views,
                "max_results": max_results,
            },
        )

        # Idempotency return if already completed
        if job.status == JobStatus.COMPLETED:
            logger.info("discovery_job_already_completed", job_id=job.id, idempotency_key=idem_key)
            result_meta = job.metadata_json or {}
            return {
                "job_id": job.id,
                "status": job.status,
                "idempotency_key": idem_key,
                "discovered_count": result_meta.get("discovered_count", 0),
                "new_sources_count": result_meta.get("new_sources_count", 0),
                "existing_sources_count": result_meta.get("existing_sources_count", 0),
                "sources": result_meta.get("sources", []),
            }

        # Start job
        JobService.start_job(session, job.id)

        try:
            # 4. Search external candidates via adapter
            candidates = adapter.search_candidates(
                topics=topics,
                keywords=keywords,
                channels=channels,
                min_views=min_views,
                published_after_days=published_after_days,
                published_after=published_after,
                published_before=published_before,
                max_results=max_results,
                max_queries=max_queries,
            )

            discovered_count = len(candidates)
            new_sources: List[Dict[str, Any]] = []
            existing_count = 0

            for cand in candidates:
                external_id = cand["external_id"]

                # Deduplication Step 1: Application-level check
                existing_source = SourceRepository.get_by_external_id(session, external_id, platform="youtube")

                if existing_source is not None:
                    existing_count += 1
                    # Check if we should record updated trend metrics (only if changed)
                    cls._maybe_record_trend_score(session, existing_source, cand)
                    new_sources.append(
                        {
                            "source_id": existing_source.id,
                            "external_id": existing_source.external_id,
                            "title": existing_source.title,
                            "is_new": False,
                            "workflow_state": existing_source.workflow_state.value,
                        }
                    )
                    continue

                # Get or create channel if channel_id is provided
                channel_entity = None
                if cand.get("channel_id"):
                    channel_entity = ChannelRepository.get_or_create(
                        session=session,
                        external_channel_id=cand["channel_id"],
                        channel_name=cand.get("channel_name") or "Unknown Channel",
                        url=f"https://www.youtube.com/channel/{cand['channel_id']}",
                        platform="youtube",
                        thumbnail_url=cand.get("thumbnail_url"),
                    )

                # Ensure published_at is timezone-aware
                published_dt = cand["published_at"]
                if isinstance(published_dt, str):
                    from app.discovery.normalization import parse_rfc3339_datetime

                    published_dt = parse_rfc3339_datetime(published_dt) or datetime.now(timezone.utc)
                elif isinstance(published_dt, datetime) and published_dt.tzinfo is None:
                    published_dt = published_dt.replace(tzinfo=timezone.utc)

                # Deduplication Step 2: Savepoint-protected creation to guarantee transaction safety
                source = Source(
                    channel_id=channel_entity.id if channel_entity else None,
                    platform="youtube",
                    external_id=external_id,
                    title=cand["title"],
                    description=cand.get("description"),
                    url=cand["url"],
                    published_at=published_dt,
                    duration_seconds=cand.get("duration_seconds", 0),
                    views=cand.get("views", 0),
                    likes=cand.get("likes", 0),
                    comments=cand.get("comments", 0),
                    workflow_state=WorkflowState.DISCOVERED,
                    source_class=SourceClass.UNKNOWN,
                    license_type=LicenseType.UNKNOWN,
                    rights_status=RightsStatus.REVIEW_REQUIRED,
                )

                created_source = None
                try:
                    with session.begin_nested():
                        SourceRepository.save(session, source)
                        created_source = source
                except IntegrityError:
                    # Concurrent duplicate caught by database uniqueness constraint
                    existing_source = SourceRepository.get_by_external_id(session, external_id, platform="youtube")
                    if existing_source:
                        existing_count += 1
                        cls._maybe_record_trend_score(session, existing_source, cand)
                        new_sources.append(
                            {
                                "source_id": existing_source.id,
                                "external_id": existing_source.external_id,
                                "title": existing_source.title,
                                "is_new": False,
                                "workflow_state": existing_source.workflow_state.value,
                            }
                        )
                        continue
                    raise

                # Calculate deterministic trend_v1 score for newly created source
                trend_res = TrendScorer.calculate_score(
                    views=created_source.views,
                    likes=created_source.likes,
                    comments=created_source.comments,
                    published_at=created_source.published_at,
                )

                trend_score = TrendScore(
                    source_id=created_source.id,
                    score=trend_res.score,
                    view_velocity=trend_res.view_velocity,
                    engagement_rate=trend_res.engagement_rate,
                    recency_score=trend_res.recency_score,
                    algorithm_version=trend_res.algorithm_version,
                    signal_snapshot=trend_res.signal_snapshot,
                    calculated_at=trend_res.calculated_at,
                )
                TrendRepository.save(session, trend_score)

                new_sources.append(
                    {
                        "source_id": created_source.id,
                        "external_id": created_source.external_id,
                        "title": created_source.title,
                        "is_new": True,
                        "trend_score": trend_res.score,
                        "workflow_state": created_source.workflow_state.value,
                    }
                )

            new_sources_count = len([s for s in new_sources if s["is_new"]])

            # Complete job
            completion_metadata = {
                "discovered_count": discovered_count,
                "new_sources_count": new_sources_count,
                "existing_sources_count": existing_count,
                "sources": new_sources,
            }
            JobService.complete_job(session, job.id, result_metadata=completion_metadata)

            # Record audit event
            AuditRepository.record_event(
                session=session,
                actor="discovery_service",
                action="YOUTUBE_DISCOVERY_COMPLETED",
                entity_type="Job",
                entity_id=job.id,
                job_id=job.id,
                request_id=request_id,
                payload={
                    "topics": topics,
                    "discovered_count": discovered_count,
                    "new_sources_count": new_sources_count,
                    "existing_sources_count": existing_count,
                },
            )

            logger.info(
                "discovery_job_succeeded",
                job_id=job.id,
                discovered=discovered_count,
                new=new_sources_count,
                existing=existing_count,
            )

            return {
                "job_id": job.id,
                "status": JobStatus.COMPLETED,
                "idempotency_key": idem_key,
                "discovered_count": discovered_count,
                "new_sources_count": new_sources_count,
                "existing_sources_count": existing_count,
                "sources": new_sources,
            }

        except Exception as exc:
            error_code = exc.code.value if isinstance(exc, AppError) else ErrorCode.INTERNAL_ERROR.value
            error_msg = str(exc)
            retryable = getattr(exc, "retryable", False)

            JobService.fail_job(
                session=session,
                job_id=job.id,
                error_code=error_code,
                error_message=error_msg,
                retryable=retryable,
            )
            logger.error("discovery_job_failed", job_id=job.id, error_code=error_code, error=error_msg)
            raise

    @classmethod
    def _maybe_record_trend_score(
        cls,
        session: Session,
        source: Source,
        candidate_data: Dict[str, Any],
    ) -> Optional[TrendScore]:
        """Record a new trend score snapshot only if metrics have changed since latest observation."""
        latest_score = TrendRepository.get_latest_by_source_id(session, source.id)

        new_views = candidate_data.get("views", source.views)
        new_likes = candidate_data.get("likes", source.likes)
        new_comments = candidate_data.get("comments", source.comments)

        if latest_score and latest_score.signal_snapshot:
            snap = latest_score.signal_snapshot
            same_views = snap.get("views") == new_views
            same_likes = snap.get("likes") == new_likes
            same_comments = snap.get("comments") == new_comments
            if same_views and same_likes and same_comments:
                # No change in metrics; avoid creating redundant duplicate trend records
                return None

        # Update source views/likes/comments to latest observation
        source.views = new_views
        source.likes = new_likes
        source.comments = new_comments
        SourceRepository.save(session, source)

        trend_res = TrendScorer.calculate_score(
            views=new_views,
            likes=new_likes,
            comments=new_comments,
            published_at=source.published_at,
        )

        trend_score = TrendScore(
            source_id=source.id,
            score=trend_res.score,
            view_velocity=trend_res.view_velocity,
            engagement_rate=trend_res.engagement_rate,
            recency_score=trend_res.recency_score,
            algorithm_version=trend_res.algorithm_version,
            signal_snapshot=trend_res.signal_snapshot,
            calculated_at=trend_res.calculated_at,
        )
        return TrendRepository.save(session, trend_score)
