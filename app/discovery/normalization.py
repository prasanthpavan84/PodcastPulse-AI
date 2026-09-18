"""Normalization of YouTube Data API payloads into standard domain candidate structures.

Metadata-only normalization ensuring no media binaries are processed or stored.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def parse_iso8601_duration(duration_str: Optional[str]) -> int:
    """Parse ISO 8601 duration (e.g., 'PT1H2M30S', 'PT45M', 'PT15S') into total seconds.

    Returns 0 for invalid, missing, or empty duration strings.
    """
    if not duration_str or not isinstance(duration_str, str):
        return 0
    match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", duration_str.strip())
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def parse_rfc3339_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """Parse RFC3339 / ISO 8601 datetime string into a timezone-aware UTC datetime.

    Returns None if date_str is missing or unparseable.
    """
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        # Replace trailing 'Z' with '+00:00' for standard fromisoformat compatibility
        cleaned = date_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def normalize_youtube_candidate(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a YouTube API video item (from videos.list) into a clean domain candidate dictionary.

    Returns None if mandatory identity (video ID) or basic structure is missing.
    """
    if not isinstance(item, dict):
        return None

    video_id = item.get("id")
    if not video_id or not isinstance(video_id, str):
        return None

    snippet = item.get("snippet", {})
    if not isinstance(snippet, dict):
        snippet = {}

    statistics = item.get("statistics", {})
    if not isinstance(statistics, dict):
        statistics = {}

    content_details = item.get("contentDetails", {})
    if not isinstance(content_details, dict):
        content_details = {}

    # Extract title
    raw_title = snippet.get("title", "")
    title = str(raw_title).strip() if raw_title is not None else ""
    if not title:
        title = f"YouTube Video {video_id}"

    # Extract description
    raw_desc = snippet.get("description")
    description = str(raw_desc).strip() if raw_desc is not None else None

    # Channel info
    channel_id = snippet.get("channelId")
    if channel_id and isinstance(channel_id, str):
        channel_id = channel_id.strip()
    else:
        channel_id = None

    channel_title = snippet.get("channelTitle")
    channel_name = str(channel_title).strip() if channel_title is not None else "Unknown Channel"

    # Thumbnail resolution preference: maxres -> high -> medium -> default
    thumbnails = snippet.get("thumbnails", {})
    thumbnail_url: Optional[str] = None
    if isinstance(thumbnails, dict):
        for quality in ("maxres", "high", "medium", "default"):
            thumb_obj = thumbnails.get(quality)
            if isinstance(thumb_obj, dict) and thumb_obj.get("url"):
                thumbnail_url = thumb_obj["url"]
                break

    # Published timestamp
    published_at = parse_rfc3339_datetime(snippet.get("publishedAt"))
    if not published_at:
        published_at = datetime.now(timezone.utc)

    # Duration in seconds
    duration_raw = content_details.get("duration")
    duration_seconds = parse_iso8601_duration(duration_raw)

    # Engagement metrics (safely converted to non-negative ints)
    def _safe_metric(val: Any) -> int:
        if val is None:
            return 0
        try:
            parsed = int(val)
            return max(0, parsed)
        except (ValueError, TypeError):
            return 0

    views = _safe_metric(statistics.get("viewCount"))
    likes = _safe_metric(statistics.get("likeCount"))
    comments = _safe_metric(statistics.get("commentCount"))

    return {
        "external_id": video_id,
        "platform": "youtube",
        "title": title,
        "description": description,
        "url": f"https://www.youtube.com/watch?v={video_id}",
        "channel_id": channel_id,
        "channel_name": channel_name,
        "thumbnail_url": thumbnail_url,
        "published_at": published_at,
        "duration_seconds": duration_seconds,
        "views": views,
        "likes": likes,
        "comments": comments,
    }
