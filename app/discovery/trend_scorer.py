"""Deterministic trend and popularity scoring engine (trend_v1).

Produces explainable, reproducible prioritization signals without AI/ML virality claims.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class TrendScoreResult:
    """Calculated trend metrics and reproducible signal snapshot."""

    score: float
    view_velocity: float
    engagement_rate: float
    recency_score: float
    algorithm_version: str
    signal_snapshot: Dict[str, Any]
    calculated_at: datetime


class TrendScorer:
    """Deterministic trend scorer implementation for trend_v1."""

    VERSION = "trend_v1"

    @classmethod
    def calculate_score(
        cls,
        views: Any,
        likes: Any,
        comments: Any,
        published_at: datetime,
        reference_time: Optional[datetime] = None,
    ) -> TrendScoreResult:
        """Calculate trend_v1 score deterministically.

        Formula components:
        1. View Velocity (views / hour): measures momentum.
        2. Engagement Rate ((likes + 2*comments) / max(1, views)): measures audience resonance.
        3. Recency Score (1 / (1 + age_hours / 720)): soft decay over a 30-day half-life.
        4. Composite Score: log10(max(1, velocity)) * (1 + 10 * engagement) * recency, normalized to 0-100.
        """
        now = reference_time or datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        age_seconds = max(60.0, (now - published_at).total_seconds())
        age_hours = age_seconds / 3600.0

        def _to_safe_int(val: Any) -> int:
            if val is None:
                return 0
            try:
                if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                    return 0
                return max(0, int(val))
            except (ValueError, TypeError):
                return 0

        safe_views = _to_safe_int(views)
        safe_likes = _to_safe_int(likes)
        safe_comments = _to_safe_int(comments)

        # 1. View Velocity (views per hour)
        view_velocity = safe_views / age_hours

        # 2. Engagement Rate
        engagement_rate = (safe_likes + (2.0 * safe_comments)) / max(1.0, float(safe_views))
        clamped_engagement = min(0.25, engagement_rate)

        # 3. Recency Score (decays smoothly over 720 hours / 30 days)
        recency_score = 1.0 / (1.0 + (age_hours / 720.0))

        # 4. Composite logarithmic scoring
        log_velocity = math.log10(max(1.0, view_velocity + 1.0))
        raw_score = log_velocity * 20.0 * (1.0 + (5.0 * clamped_engagement)) * recency_score
        final_score = round(min(100.0, max(0.0, raw_score)), 2)

        snapshot = {
            "views": safe_views,
            "likes": safe_likes,
            "comments": safe_comments,
            "published_at": published_at.isoformat(),
            "reference_time": now.isoformat(),
            "age_hours": round(age_hours, 2),
            "view_velocity": round(view_velocity, 2),
            "engagement_rate": round(engagement_rate, 4),
            "recency_score": round(recency_score, 4),
            "raw_score": round(raw_score, 4),
            "final_score": final_score,
            "algorithm_version": cls.VERSION,
        }

        return TrendScoreResult(
            score=final_score,
            view_velocity=round(view_velocity, 2),
            engagement_rate=round(engagement_rate, 4),
            recency_score=round(recency_score, 4),
            algorithm_version=cls.VERSION,
            signal_snapshot=snapshot,
            calculated_at=now,
        )
