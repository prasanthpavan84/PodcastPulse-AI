"""Unit tests for deterministic popularity scoring engine (popularity_v1)."""

from datetime import datetime, timedelta, timezone

from app.domain.popularity.scorer import (
    POPULARITY_ALGORITHM_VERSION,
    PopularityScorer,
)


def test_popularity_scoring_is_strictly_deterministic():
    """Identical inputs must produce bit-for-bit identical scores and snapshots."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    pub_time = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)

    res1 = PopularityScorer.calculate_score(
        published_at=pub_time,
        views=150000,
        likes=8000,
        comments=450,
        duration_seconds=1800,
        reference_time=ref_time,
    )
    res2 = PopularityScorer.calculate_score(
        published_at=pub_time,
        views=150000,
        likes=8000,
        comments=450,
        duration_seconds=1800,
        reference_time=ref_time,
    )

    assert res1.final_score == res2.final_score
    assert res1.algorithm_version == POPULARITY_ALGORITHM_VERSION
    assert res1.component_scores == res2.component_scores
    assert res1.missing_inputs == res2.missing_inputs
    assert res1.rationale == res2.rationale
    assert res1.input_snapshot == res2.input_snapshot


def test_popularity_scorer_handles_missing_metadata_without_fabrication():
    """Missing metadata (None) must not be converted to 0; missing components are omitted and tracked."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    pub_time = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)

    # Views missing (None), likes and comments present
    res = PopularityScorer.calculate_score(
        published_at=pub_time,
        views=None,
        likes=500,
        comments=25,
        duration_seconds=900,
        reference_time=ref_time,
    )

    assert "views" in res.missing_inputs
    assert "views_velocity" not in res.component_scores
    # Engagement requires views, so engagement cannot be calculated
    assert "engagement" not in res.component_scores
    assert "recency" in res.component_scores
    assert "duration_fit" in res.component_scores

    # Verify input_snapshot preserved None
    assert res.input_snapshot["views"] is None
    assert res.input_snapshot["likes"] == 500

    # Rationale explicitly notes missing views
    assert "views" in res.rationale


def test_zero_values_are_treated_as_valid_inputs():
    """views = 0 is a semantically valid observation, not a missing input."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    pub_time = datetime(2026, 9, 14, 12, 0, 0, tzinfo=timezone.utc)

    res = PopularityScorer.calculate_score(
        published_at=pub_time,
        views=0,
        likes=0,
        comments=0,
        duration_seconds=600,
        reference_time=ref_time,
    )

    assert "views" not in res.missing_inputs
    assert "likes" not in res.missing_inputs
    assert "views_velocity" in res.component_scores
    assert res.component_scores["views_velocity"] == 0.0
    assert res.component_scores["engagement"] == 0.0


def test_weight_normalization_across_available_components():
    """Score must normalize over the sum of weights for available components."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    pub_time = datetime(2026, 9, 15, 11, 0, 0, tzinfo=timezone.utc)  # 1 hour old

    # Only published_at and duration_seconds are provided
    res = PopularityScorer.calculate_score(
        published_at=pub_time,
        duration_seconds=1200,  # 20 mins -> duration_fit = 100
        reference_time=ref_time,
    )

    # Available components: recency (weight 0.20) and duration_fit (weight 0.10)
    assert set(res.component_scores.keys()) == {"recency", "duration_fit"}
    # Recency for 1 hour old is close to 100 (100 / (1 + 1/720) ~= 99.86)
    # Duration_fit is 100.0
    # Weighted average should be very close to 99.9
    assert 98.0 <= res.final_score <= 100.0
    assert set(res.missing_inputs) == {"comments", "duration_seconds", "likes", "views"} - {"duration_seconds"}


def test_recency_decay_smoothness():
    """New content must score higher on recency than content that is months old."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)

    fresh_pub = ref_time - timedelta(hours=2)
    old_pub = ref_time - timedelta(days=90)

    res_fresh = PopularityScorer.calculate_score(published_at=fresh_pub, reference_time=ref_time)
    res_old = PopularityScorer.calculate_score(published_at=old_pub, reference_time=ref_time)

    assert res_fresh.component_scores["recency"] > res_old.component_scores["recency"]
    assert res_fresh.final_score > res_old.final_score


def test_duration_fit_scoring():
    """Podcast durations suited for shorts extraction score higher than very short clips."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    pub = ref_time - timedelta(days=1)

    # 30-minute podcast: optimal fit
    res_podcast = PopularityScorer.calculate_score(published_at=pub, duration_seconds=1800, reference_time=ref_time)
    # 30-second snippet: poor fit
    res_tiny = PopularityScorer.calculate_score(published_at=pub, duration_seconds=30, reference_time=ref_time)

    assert res_podcast.component_scores["duration_fit"] > res_tiny.component_scores["duration_fit"]


def test_rationale_is_deterministic_and_contains_no_llm_hallucinations():
    """Rationale must be a structured explainable string detailing the exact calculation."""
    ref_time = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    pub = ref_time - timedelta(days=2)

    res = PopularityScorer.calculate_score(
        published_at=pub,
        views=50000,
        likes=2500,
        comments=120,
        duration_seconds=2400,
        reference_time=ref_time,
    )

    assert "popularity_v1" in res.rationale
    assert "Active components:" in res.rationale
    assert "Normalized weight:" in res.rationale
    assert isinstance(res.rationale, str)
