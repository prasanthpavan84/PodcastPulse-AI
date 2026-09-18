"""Unit tests for deterministic TrendScorer (trend_v1)."""

import math
from datetime import datetime, timedelta, timezone

from app.discovery.trend_scorer import TrendScorer


def test_trend_scoring_is_strictly_deterministic():
    """Verify that identical inputs produce the exact same score and signal snapshot."""
    pub_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    ref_time = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    res1 = TrendScorer.calculate_score(
        views=50000,
        likes=2500,
        comments=300,
        published_at=pub_time,
        reference_time=ref_time,
    )
    res2 = TrendScorer.calculate_score(
        views=50000,
        likes=2500,
        comments=300,
        published_at=pub_time,
        reference_time=ref_time,
    )

    assert res1.score == res2.score
    assert res1.view_velocity == res2.view_velocity
    assert res1.engagement_rate == res2.engagement_rate
    assert res1.recency_score == res2.recency_score
    assert res1.algorithm_version == "trend_v1"
    assert res1.signal_snapshot == res2.signal_snapshot


def test_trend_scoring_relative_momentum():
    """Verify high-velocity and engaged content scores significantly higher than low-velocity content."""
    ref_time = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    recent_pub = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)

    # Viral high-velocity video (100k views in 24 hours, 5k likes)
    viral = TrendScorer.calculate_score(
        views=100000,
        likes=5000,
        comments=800,
        published_at=recent_pub,
        reference_time=ref_time,
    )

    # Slow video (200 views in 24 hours, 2 likes)
    slow = TrendScorer.calculate_score(
        views=200,
        likes=2,
        comments=0,
        published_at=recent_pub,
        reference_time=ref_time,
    )

    assert viral.score > slow.score
    assert viral.view_velocity > slow.view_velocity
    assert 0.0 <= viral.score <= 100.0
    assert 0.0 <= slow.score <= 100.0


def test_zero_and_missing_metrics_handled_safely():
    """Verify 0 views, 0 likes, 0 comments or None values do not raise ZeroDivisionError or TypeError."""
    pub_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    ref_time = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    res_zero = TrendScorer.calculate_score(
        views=0,
        likes=0,
        comments=0,
        published_at=pub_time,
        reference_time=ref_time,
    )
    assert res_zero.score == 0.0
    assert res_zero.view_velocity == 0.0
    assert res_zero.engagement_rate == 0.0

    res_none = TrendScorer.calculate_score(
        views=None,
        likes=None,
        comments=None,
        published_at=pub_time,
        reference_time=ref_time,
    )
    assert res_none.score == 0.0
    assert res_none.view_velocity == 0.0


def test_invalid_and_negative_metrics_clamped():
    """Verify negative numbers or invalid values are clamped safely to non-negative values."""
    pub_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    ref_time = datetime(2026, 9, 2, 12, 0, 0, tzinfo=timezone.utc)

    res = TrendScorer.calculate_score(
        views=-5000,
        likes=-10,
        comments="invalid",
        published_at=pub_time,
        reference_time=ref_time,
    )
    assert res.score == 0.0
    assert res.view_velocity == 0.0
    assert not math.isnan(res.score)
    assert not math.isinf(res.score)


def test_future_timestamp_clamped_safely():
    """Verify published_at in the future is clamped to minimum age without negative age or division errors."""
    ref_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    future_pub = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)

    res = TrendScorer.calculate_score(
        views=1000,
        likes=50,
        comments=10,
        published_at=future_pub,
        reference_time=ref_time,
    )
    assert 0.0 <= res.score <= 100.0
    assert res.view_velocity > 0


def test_old_content_recency_decay():
    """Verify older content experiences continuous recency decay."""
    ref_time = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
    one_day_old = ref_time - timedelta(days=1)
    one_year_old = ref_time - timedelta(days=365)

    recent = TrendScorer.calculate_score(
        views=50000,
        likes=1000,
        comments=100,
        published_at=one_day_old,
        reference_time=ref_time,
    )
    old = TrendScorer.calculate_score(
        views=50000,
        likes=1000,
        comments=100,
        published_at=one_year_old,
        reference_time=ref_time,
    )

    assert recent.recency_score > old.recency_score
    assert recent.score > old.score
    assert old.recency_score > 0.0
