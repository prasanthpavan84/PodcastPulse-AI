"""Unit tests for DiscoveryQueryBuilder."""

from datetime import datetime, timedelta, timezone

import pytest

from app.core.errors import DomainValidationError
from app.discovery.query_builder import DiscoveryQueryBuilder


def test_topic_only_query_generation():
    """Verify clean topic list produces expected discovery queries."""
    queries = DiscoveryQueryBuilder.build_queries(
        topics=["Artificial Intelligence", "Podcast Production"],
        max_results=20,
    )
    assert len(queries) == 2
    assert queries[0].query_term == "Artificial Intelligence"
    assert queries[0].max_results == 20
    assert queries[1].query_term == "Podcast Production"


def test_topic_and_keyword_matrix_generation():
    """Verify combination of topics and keywords generates expected cross-product queries."""
    queries = DiscoveryQueryBuilder.build_queries(
        topics=["AI"],
        keywords=["tools", "news"],
        max_queries_per_run=10,
    )
    assert len(queries) == 2
    terms = [q.query_term for q in queries]
    assert "AI tools" in terms
    assert "AI news" in terms


def test_channel_targeted_query_generation():
    """Verify channel IDs produce targeted channel query entries."""
    queries = DiscoveryQueryBuilder.build_queries(
        topics=["Tech"],
        channels=["UC_channel_123", "UC_channel_456"],
        max_queries_per_run=5,
    )
    # 1 topic query + 2 channel queries
    assert len(queries) == 3
    channel_ids = [q.channel_id for q in queries if q.channel_id]
    assert "UC_channel_123" in channel_ids
    assert "UC_channel_456" in channel_ids


def test_date_filtering_rfc3339():
    """Verify published_after and published_before produce properly formatted RFC3339 UTC strings."""
    t_after = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    t_before = datetime(2026, 8, 15, 10, 0, 0, tzinfo=timezone.utc)

    queries = DiscoveryQueryBuilder.build_queries(
        topics=["Robotics"],
        published_after=t_after,
        published_before=t_before,
    )
    assert len(queries) == 1
    assert queries[0].published_after == "2026-08-01T10:00:00Z"
    assert queries[0].published_before == "2026-08-15T10:00:00Z"


def test_published_after_days_relative_calculation():
    """Verify published_after_days relative cutoff string."""
    queries = DiscoveryQueryBuilder.build_queries(
        topics=["Machine Learning"],
        published_after_days=7,
    )
    assert len(queries) == 1
    assert queries[0].published_after is not None
    # Verify it ends with Z
    assert queries[0].published_after.endswith("Z")


def test_bounded_max_queries_enforcement():
    """Verify query builder respects max_queries_per_run limit."""
    queries = DiscoveryQueryBuilder.build_queries(
        topics=["Topic1", "Topic2", "Topic3", "Topic4", "Topic5"],
        keywords=["kw1", "kw2"],
        max_queries_per_run=3,
    )
    assert len(queries) == 3


def test_validation_rejects_empty_inputs():
    """Verify empty configuration raises DomainValidationError."""
    with pytest.raises(DomainValidationError, match="requires at least one non-empty topic, keyword, or channel"):
        DiscoveryQueryBuilder.build_queries(topics=[], keywords=[], channels=[])

    with pytest.raises(DomainValidationError, match="requires at least one non-empty topic, keyword, or channel"):
        DiscoveryQueryBuilder.build_queries(topics=["   "], keywords=["  "])


def test_validation_rejects_invalid_max_results():
    """Verify max_results boundary limits (1 to 50) are enforced."""
    with pytest.raises(DomainValidationError, match="max_results must be between 1 and 50"):
        DiscoveryQueryBuilder.build_queries(topics=["AI"], max_results=0)

    with pytest.raises(DomainValidationError, match="max_results must be between 1 and 50"):
        DiscoveryQueryBuilder.build_queries(topics=["AI"], max_results=51)


def test_validation_rejects_inverted_dates():
    """Verify published_after cannot be later than published_before."""
    now = datetime.now(timezone.utc)
    earlier = now - timedelta(days=5)
    with pytest.raises(DomainValidationError, match="published_after cannot be later than published_before"):
        DiscoveryQueryBuilder.build_queries(
            topics=["Tech"],
            published_after=now,
            published_before=earlier,
        )
