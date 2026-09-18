"""Official YouTube Data API v3 adapter for content discovery."""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from app.adapters.interfaces import YouTubeDiscovery
from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.discovery.normalization import normalize_youtube_candidate, parse_iso8601_duration
from app.discovery.query_builder import DiscoveryQueryBuilder

logger = get_logger("youtube_adapter")


class YouTubeAPIAdapter(YouTubeDiscovery):
    """Production adapter for YouTube Data API v3 with strict error handling and credential sanitization."""

    BASE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
    BASE_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self, api_key: Optional[str] = None, timeout: float = 15.0):
        self.api_key = api_key or settings.youtube_api_key
        self.timeout = timeout

    def _sanitize_text(self, text: Optional[str]) -> str:
        """Strip API keys and sensitive tokens from error strings and URLs."""
        if not text:
            return ""
        sanitized = str(text)
        if self.api_key:
            sanitized = sanitized.replace(self.api_key, "***REDACTED***")
        sanitized = re.sub(r"key=[^&\s]+", "key=***REDACTED***", sanitized)
        sanitized = re.sub(r"Bearer\s+[^&\s]+", "Bearer ***REDACTED***", sanitized)
        return sanitized

    def search_candidates(
        self,
        topics: List[str],
        keywords: Optional[List[str]] = None,
        channels: Optional[List[str]] = None,
        min_views: int = 10000,
        published_after_days: Optional[int] = 30,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        max_results: int = 25,
        max_queries: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Query YouTube Data API across bounded queries and return normalized candidate metadata."""
        if not self.api_key:
            raise AppError(
                code=ErrorCode.CONFIGURATION_ERROR,
                message="YouTube API key is not configured. Set YOUTUBE_API_KEY in .env.",
                status_code=500,
            )

        limit_queries = max_queries or settings.discovery_max_queries_per_run
        queries = DiscoveryQueryBuilder.build_queries(
            topics=topics,
            keywords=keywords,
            channels=channels,
            published_after_days=published_after_days,
            published_after=published_after,
            published_before=published_before,
            max_results=max_results,
            max_queries_per_run=limit_queries,
        )

        all_candidates: List[Dict[str, Any]] = []
        seen_ids = set()

        with httpx.Client(timeout=self.timeout) as client:
            for q in queries:
                try:
                    candidates = self._execute_search_query(client, q, min_views=min_views)
                    for c in candidates:
                        v_id = c["external_id"]
                        if v_id not in seen_ids:
                            seen_ids.add(v_id)
                            all_candidates.append(c)
                except httpx.TimeoutException as exc:
                    logger.error("youtube_api_timeout", query=self._sanitize_text(q.query_term))
                    raise AppError(
                        code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                        message="Connection timeout while contacting YouTube Data API.",
                        status_code=504,
                        retryable=True,
                    ) from exc
                except httpx.HTTPStatusError as exc:
                    self._handle_http_error(exc)

        logger.info("youtube_discovery_completed", candidate_count=len(all_candidates))
        return all_candidates

    def _execute_search_query(self, client: httpx.Client, query, min_views: int) -> List[Dict[str, Any]]:
        """Execute search list query and hydrate with detailed statistics."""
        params: Dict[str, Any] = {
            "part": "snippet",
            "type": "video",
            "q": query.query_term,
            "maxResults": min(50, query.max_results),
            "key": self.api_key,
        }
        if query.channel_id:
            params["channelId"] = query.channel_id
        if query.published_after:
            params["publishedAfter"] = query.published_after
        if query.published_before:
            params["publishedBefore"] = query.published_before

        res = client.get(self.BASE_SEARCH_URL, params=params)
        res.raise_for_status()
        data = res.json()

        items = data.get("items", [])
        video_ids = [
            item.get("id", {}).get("videoId")
            for item in items
            if isinstance(item, dict)
            and item.get("id", {}).get("kind") == "youtube#video"
            and item.get("id", {}).get("videoId")
        ]

        if not video_ids:
            return []

        # Hydrate video details (statistics, duration, etc.)
        return self._hydrate_video_details(client, video_ids, min_views)

    def _hydrate_video_details(
        self, client: httpx.Client, video_ids: List[str], min_views: int
    ) -> List[Dict[str, Any]]:
        """Fetch statistics and contentDetails for batch of video IDs."""
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": ",".join(video_ids),
            "key": self.api_key,
        }
        res = client.get(self.BASE_VIDEOS_URL, params=params)
        res.raise_for_status()
        details_data = res.json()

        candidates: List[Dict[str, Any]] = []
        for item in details_data.get("items", []):
            candidate = normalize_youtube_candidate(item)
            if candidate and candidate.get("views", 0) >= min_views:
                candidates.append(candidate)

        return candidates

    def _handle_http_error(self, exc: httpx.HTTPStatusError) -> None:
        """Categorize YouTube API HTTP errors into structured application errors with secret sanitization."""
        status_code = exc.response.status_code
        try:
            err_json = exc.response.json()
            errors = err_json.get("error", {}).get("errors", [])
            reason = errors[0].get("reason", "") if errors else ""
            raw_msg = err_json.get("error", {}).get("message", exc.response.text)
        except Exception:
            reason = ""
            raw_msg = exc.response.text

        msg = self._sanitize_text(raw_msg)
        logger.error("youtube_api_http_error", status_code=status_code, reason=reason)

        if status_code == 403 and reason in {"quotaExceeded", "dailyLimitExceeded"}:
            raise AppError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"YouTube Data API quota exceeded: {msg}",
                status_code=429,
                retryable=False,
                details={"reason": reason},
            ) from exc

        if status_code == 400 and reason in {"keyInvalid", "badRequest"}:
            raise AppError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message=f"Invalid YouTube Data API request or key: {msg}",
                status_code=400,
                retryable=False,
                details={"reason": reason},
            ) from exc

        raise AppError(
            code=ErrorCode.EXTERNAL_SERVICE_ERROR,
            message=f"YouTube Data API error (status {status_code}): {msg}",
            status_code=status_code,
            retryable=(status_code in {429, 500, 502, 503}),
            details={"reason": reason},
        ) from exc


__all__ = ["YouTubeAPIAdapter", "parse_iso8601_duration"]
