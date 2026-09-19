"""Deterministic, versioned popularity scoring engine (popularity_v1).

Produces explainable, reproducible popularity prioritization signals without fabricating
missing values or conflating popularity with rights.
"""

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

POPULARITY_ALGORITHM_VERSION = "popularity_v1"

COMPONENT_WEIGHTS: Dict[str, float] = {
    "views_velocity": 0.35,
    "engagement": 0.35,
    "recency": 0.20,
    "duration_fit": 0.10,
}


@dataclass(frozen=True)
class PopularityScoreResult:
    """Outcome of deterministic popularity scoring."""

    algorithm_version: str
    final_score: float
    component_scores: Dict[str, float]
    missing_inputs: List[str]
    input_snapshot: Dict[str, Any]
    rationale: str
    scored_at: datetime


class PopularityScorer:
    """Deterministic, versioned popularity scorer for popularity_v1."""

    VERSION = POPULARITY_ALGORITHM_VERSION

    @classmethod
    def calculate_score(
        cls,
        published_at: datetime,
        views: Optional[int] = None,
        likes: Optional[int] = None,
        comments: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        channel_signals: Optional[Dict[str, Any]] = None,
        reference_time: Optional[datetime] = None,
    ) -> PopularityScoreResult:
        """Calculate popularity score deterministically.

        Rules:
        - Do NOT convert NULL -> 0 for missing metrics.
        - Omit unavailable components and normalize over available component weights.
        - Record which components were unavailable in missing_inputs.
        - Preserve original input values in input_snapshot.
        - Generate an explainable, deterministic rationale.
        """
        now = reference_time or datetime.now(timezone.utc)
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        # Snapshot original inputs exactly as provided
        input_snapshot: Dict[str, Any] = {
            "views": views,
            "likes": likes,
            "comments": comments,
            "duration_seconds": duration_seconds,
            "published_at": published_at.isoformat(),
            "channel_signals": channel_signals,
            "reference_time": now.isoformat(),
        }

        missing_inputs: List[str] = []
        component_scores: Dict[str, float] = {}

        # 1. Recency component (Always available from published_at)
        age_seconds = max(0.0, (now - published_at).total_seconds())
        age_hours = max(0.01, age_seconds / 3600.0)
        # 30-day half-life decay (720 hours)
        recency_factor = 1.0 / (1.0 + (age_hours / 720.0))
        recency_score = round(min(100.0, max(0.0, recency_factor * 100.0)), 2)
        component_scores["recency"] = recency_score

        # 2. View Velocity component (requires valid views)
        if views is None:
            missing_inputs.append("views")
        else:
            try:
                safe_views = max(0, int(views))
                # Hourly velocity
                hourly_velocity = safe_views / age_hours
                # Logarithmic scaling: 10,000 views/hr ~= 100 score
                log_velocity = math.log10(max(1.0, hourly_velocity + 1.0))
                velocity_score = round(min(100.0, max(0.0, log_velocity * 25.0)), 2)
                component_scores["views_velocity"] = velocity_score
            except (ValueError, TypeError):
                missing_inputs.append("views")

        # 3. Engagement component (requires views and likes)
        if likes is None:
            missing_inputs.append("likes")
        if comments is None:
            missing_inputs.append("comments")

        if views is not None and likes is not None:
            try:
                safe_v = max(0, int(views))
                safe_l = max(0, int(likes))
                safe_c = max(0, int(comments)) if comments is not None else 0
                if safe_v > 0:
                    engagement_ratio = (float(safe_l) + (2.0 * float(safe_c))) / float(safe_v)
                    # 10% engagement ratio reaches maximum 100 points
                    engagement_score = round(min(100.0, max(0.0, (engagement_ratio / 0.10) * 100.0)), 2)
                    component_scores["engagement"] = engagement_score
                else:
                    component_scores["engagement"] = 0.0
            except (ValueError, TypeError):
                pass

        else:
            # Cannot calculate engagement without views or likes
            pass

        # 4. Duration fit component (requires duration_seconds)
        if duration_seconds is None:
            missing_inputs.append("duration_seconds")
        else:
            try:
                dur = max(0, int(duration_seconds))
                # Ideal podcast episode length for shorts extraction: 5 mins to 2 hours
                if 300 <= dur <= 7200:
                    duration_score = 100.0
                elif dur < 300:
                    duration_score = max(10.0, (dur / 300.0) * 100.0)
                else:
                    duration_score = max(20.0, 100.0 - (((dur - 7200) / 7200.0) * 50.0))
                component_scores["duration_fit"] = round(min(100.0, max(0.0, duration_score)), 2)
            except (ValueError, TypeError):
                missing_inputs.append("duration_seconds")

        # Normalize score over available component weights
        available_weight = sum(COMPONENT_WEIGHTS[c] for c in component_scores if c in COMPONENT_WEIGHTS)
        if available_weight > 0.0:
            weighted_sum = sum(
                component_scores[c] * COMPONENT_WEIGHTS[c] for c in component_scores if c in COMPONENT_WEIGHTS
            )
            final_score = round(min(100.0, max(0.0, weighted_sum / available_weight)), 2)
        else:
            final_score = 0.0

        # Construct deterministic rationale
        components_summary = ", ".join(
            f"{c}: {component_scores[c]:.2f} (weight: {COMPONENT_WEIGHTS.get(c, 0.0):.2f})"
            for c in sorted(component_scores.keys())
        )
        missing_summary = ", ".join(sorted(missing_inputs)) if missing_inputs else "none"

        rationale = (
            f"Calculated {cls.VERSION} score: {final_score:.2f}. "
            f"Active components: [{components_summary}]. "
            f"Normalized weight: {available_weight:.2f}/1.00. "
            f"Missing inputs omitted: [{missing_summary}]."
        )

        return PopularityScoreResult(
            algorithm_version=cls.VERSION,
            final_score=final_score,
            component_scores=component_scores,
            missing_inputs=sorted(list(set(missing_inputs))),
            input_snapshot=input_snapshot,
            rationale=rationale,
            scored_at=now,
        )
