"""Integration tests for YouTube discovery, deduplication, and trend persistence running against MySQL 8."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.mocks import MockYouTubeDiscovery
from app.database.models.source import Source
from app.database.models.trend import TrendScore
from app.domain.enums import RightsStatus, WorkflowState
from app.repositories.source_repository import SourceRepository
from app.repositories.trend_repository import TrendRepository
from app.services.discovery_service import DiscoveryService


def test_mysql_trend_score_persistence_and_retrieval(mysql_session: Session):
    """Verify TrendScore persistence, index queries, and retrieval methods in MySQL 8."""
    # Create parent source
    source = Source(
        platform="youtube",
        external_id="yt_trend_test_001",
        title="Trend Test Video",
        url="https://youtube.com/watch?v=yt_trend_test_001",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
    )
    SourceRepository.save(mysql_session, source)

    # Persist trend score
    score_record = TrendScore(
        source_id=source.id,
        score=78.5,
        view_velocity=1250.0,
        engagement_rate=0.045,
        recency_score=0.92,
        algorithm_version="trend_v1",
        signal_snapshot={"views": 50000, "likes": 2000, "comments": 250},
    )
    TrendRepository.save(mysql_session, score_record)

    # Lookup by ID
    fetched = TrendRepository.get_by_id(mysql_session, score_record.id)
    assert fetched is not None
    assert fetched.source_id == source.id
    assert fetched.score == 78.5
    assert fetched.algorithm_version == "trend_v1"

    # Lookup latest by source ID
    latest = TrendRepository.get_latest_by_source_id(mysql_session, source.id)
    assert latest is not None
    assert latest.id == score_record.id

    # List all by source ID
    history = TrendRepository.list_by_source_id(mysql_session, source.id)
    assert len(history) == 1


def test_mysql_discovery_workflow_and_rights_safety(mysql_session: Session):
    """Verify discovery creates source in DISCOVERED and REVIEW_REQUIRED state with no rights inferred."""
    mock_candidate = {
        "external_id": "yt_rights_guard_123",
        "platform": "youtube",
        "title": "Unapproved Public Video",
        "description": "Public interview",
        "channel_id": "UC_rights_chan_01",
        "channel_name": "Rights Channel",
        "thumbnail_url": "https://img.youtube.com/vi/yt_rights_guard_123/hqdefault.jpg",
        "url": "https://youtube.com/watch?v=yt_rights_guard_123",
        "published_at": datetime.now(timezone.utc),
        "duration_seconds": 1800,
        "views": 35000,
        "likes": 1200,
        "comments": 95,
    }

    adapter = MockYouTubeDiscovery(canned_candidates=[mock_candidate])

    result = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter,
        topics=["Podcasting"],
        idempotency_key="discovery_rights_safety_test_v1",
    )

    assert result["discovered_count"] == 1
    assert result["new_sources_count"] == 1

    source = SourceRepository.get_by_external_id(mysql_session, "yt_rights_guard_123")
    assert source is not None
    # Crucial Rights Safety checks
    assert source.workflow_state == WorkflowState.DISCOVERED
    assert source.rights_status == RightsStatus.REVIEW_REQUIRED


def test_mysql_deduplication_and_trend_history_behavior(mysql_session: Session):
    """Verify multi-level deduplication: first creates source, second does not duplicate, and avoids redundant trend records."""
    candidate = {
        "external_id": "yt_dedup_test_888",
        "platform": "youtube",
        "title": "Deduplication Subject",
        "url": "https://youtube.com/watch?v=yt_dedup_test_888",
        "published_at": datetime.now(timezone.utc),
        "duration_seconds": 600,
        "views": 40000,
        "likes": 1500,
        "comments": 100,
    }

    adapter = MockYouTubeDiscovery(canned_candidates=[candidate])

    # 1. First discovery run
    run1 = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter,
        topics=["Tech"],
        idempotency_key="dedup_run_first_1",
    )
    assert run1["new_sources_count"] == 1
    assert run1["existing_sources_count"] == 0

    source = SourceRepository.get_by_external_id(mysql_session, "yt_dedup_test_888")
    assert source is not None
    scores_initial = TrendRepository.list_by_source_id(mysql_session, source.id)
    assert len(scores_initial) == 1

    # 2. Second discovery run with identical candidate metrics
    run2 = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter,
        topics=["Tech"],
        idempotency_key="dedup_run_second_2",
    )
    assert run2["new_sources_count"] == 0
    assert run2["existing_sources_count"] == 1

    # Ensure no duplicate source was created
    all_sources = SourceRepository.list_sources(mysql_session, limit=100)
    matching = [s for s in all_sources if s.external_id == "yt_dedup_test_888"]
    assert len(matching) == 1

    # Verify no redundant duplicate trend score was created for unchanged metrics
    scores_after_same = TrendRepository.list_by_source_id(mysql_session, source.id)
    assert len(scores_after_same) == 1

    # 3. Third discovery run with updated metrics (growth)
    updated_candidate = dict(candidate)
    updated_candidate["views"] = 85000
    updated_candidate["likes"] = 3500
    adapter_updated = MockYouTubeDiscovery(canned_candidates=[updated_candidate])

    run3 = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter_updated,
        topics=["Tech"],
        idempotency_key="dedup_run_third_3",
    )
    assert run3["existing_sources_count"] == 1

    # Verify a new trend observation snapshot IS recorded when metrics change
    scores_after_change = TrendRepository.list_by_source_id(mysql_session, source.id)
    assert len(scores_after_change) == 2
    recorded_views = [s.signal_snapshot["views"] for s in scores_after_change]
    assert 85000 in recorded_views
    assert 40000 in recorded_views


def test_mysql_database_uniqueness_constraint_fallback(mysql_session: Session):
    """Verify MySQL 8 uniqueness constraint triggers on external_id duplicate insertion."""
    s1 = Source(
        platform="youtube",
        external_id="yt_db_constraint_test",
        title="Source Alpha",
        url="https://youtube.com/watch?v=alpha",
        published_at=datetime.now(timezone.utc),
    )
    SourceRepository.save(mysql_session, s1)
    mysql_session.flush()

    s2 = Source(
        platform="youtube",
        external_id="yt_db_constraint_test",
        title="Source Beta",
        url="https://youtube.com/watch?v=beta",
        published_at=datetime.now(timezone.utc),
    )
    # Using nested transaction / savepoint to safely test constraint violation without breaking session
    with pytest.raises(IntegrityError):
        with mysql_session.begin_nested():
            mysql_session.add(s2)
            mysql_session.flush()
