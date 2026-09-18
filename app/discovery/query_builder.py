"""Deterministic query builder for YouTube content discovery."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from app.core.errors import DomainValidationError


@dataclass(frozen=True)
class DiscoveryQuery:
    """Deterministic search query specification for YouTube API."""

    query_term: str
    channel_id: Optional[str] = None
    published_after: Optional[str] = None
    published_before: Optional[str] = None
    max_results: int = 25


class DiscoveryQueryBuilder:
    """Builds deterministic, bounded YouTube search queries with strict configuration validation."""

    @staticmethod
    def build_queries(
        topics: List[str],
        keywords: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
        published_after_days: Optional[int] = 30,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        max_results: int = 25,
        max_queries_per_run: int = 5,
    ) -> List[DiscoveryQuery]:
        """Construct bounded list of discovery queries respecting max_queries_per_run and validating inputs."""
        clean_topics = [t.strip() for t in (topics or []) if t.strip()]
        clean_keywords = [k.strip() for k in (keywords or []) if k.strip()]
        clean_channels = [c.strip() for c in (channels or []) if c.strip()]

        if not clean_topics and not clean_keywords and not clean_channels:
            raise DomainValidationError(
                "Discovery query configuration requires at least one non-empty topic, keyword, or channel."
            )

        if max_results < 1 or max_results > 50:
            raise DomainValidationError(
                f"max_results must be between 1 and 50 (YouTube Data API limits), got {max_results}."
            )

        if max_queries_per_run < 1:
            raise DomainValidationError(f"max_queries_per_run must be at least 1, got {max_queries_per_run}.")

        if published_after and published_before:
            p_after = published_after if published_after.tzinfo else published_after.replace(tzinfo=timezone.utc)
            p_before = published_before if published_before.tzinfo else published_before.replace(tzinfo=timezone.utc)
            if p_after > p_before:
                raise DomainValidationError("published_after cannot be later than published_before.")

        # Calculate RFC3339 date strings
        pub_after_str: Optional[str] = None
        if published_after:
            pub_after_str = published_after.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        elif published_after_days is not None and published_after_days > 0:
            cutoff = datetime.now(timezone.utc) - timedelta(days=published_after_days)
            pub_after_str = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

        pub_before_str: Optional[str] = None
        if published_before:
            pub_before_str = published_before.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        queries: List[DiscoveryQuery] = []

        # 1. Topic + Keyword combinations
        topic_seeds = clean_topics if clean_topics else ([""] if clean_keywords else [])

        for topic in topic_seeds:
            if clean_keywords:
                for kw in clean_keywords:
                    term = f"{topic} {kw}".strip()
                    queries.append(
                        DiscoveryQuery(
                            query_term=term,
                            published_after=pub_after_str,
                            published_before=pub_before_str,
                            max_results=max_results,
                        )
                    )
            else:
                if topic:
                    queries.append(
                        DiscoveryQuery(
                            query_term=topic,
                            published_after=pub_after_str,
                            published_before=pub_before_str,
                            max_results=max_results,
                        )
                    )

        # 2. Targeted channel queries
        for ch_id in clean_channels:
            queries.append(
                DiscoveryQuery(
                    query_term=clean_topics[0] if clean_topics else "",
                    channel_id=ch_id,
                    published_after=pub_after_str,
                    published_before=pub_before_str,
                    max_results=max_results,
                )
            )

        # Enforce deterministic limit
        return queries[:max_queries_per_run]
