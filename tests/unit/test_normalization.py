"""Unit tests for YouTube candidate payload normalization."""

from app.discovery.normalization import (
    normalize_youtube_candidate,
    parse_iso8601_duration,
    parse_rfc3339_datetime,
)


def test_parse_iso8601_duration_variations():
    """Verify ISO 8601 duration string parser handles standard durations and edge cases."""
    assert parse_iso8601_duration("PT1H2M30S") == 3750
    assert parse_iso8601_duration("PT45M") == 2700
    assert parse_iso8601_duration("PT15S") == 15
    assert parse_iso8601_duration("PT2H") == 7200
    assert parse_iso8601_duration("PT0S") == 0
    assert parse_iso8601_duration("") == 0
    assert parse_iso8601_duration(None) == 0
    assert parse_iso8601_duration("INVALID_FORMAT") == 0


def test_parse_rfc3339_datetime():
    """Verify RFC3339 timestamp parser converts to UTC datetime."""
    dt = parse_rfc3339_datetime("2026-09-01T15:30:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 9
    assert dt.day == 1
    assert dt.hour == 15
    assert dt.tzinfo is not None

    assert parse_rfc3339_datetime(None) is None
    assert parse_rfc3339_datetime("not-a-date") is None


def test_normalize_full_representative_youtube_payload():
    """Verify conversion of a complete YouTube API video item into domain candidate dictionary."""
    raw_item = {
        "id": "dQw4w9WgXcQ",
        "snippet": {
            "title": "Rick Astley - Never Gonna Give You Up (Official Music Video)",
            "description": "The official video for Never Gonna Give You Up.",
            "channelId": "UCuAXFkgsw1L7xaCfnd5JJOw",
            "channelTitle": "Rick Astley",
            "publishedAt": "2009-10-25T06:57:33Z",
            "thumbnails": {
                "default": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg"},
                "high": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"},
                "maxres": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"},
            },
        },
        "contentDetails": {
            "duration": "PT3M33S",
        },
        "statistics": {
            "viewCount": "1500000000",
            "likeCount": "17000000",
            "commentCount": "2500000",
        },
    }

    normalized = normalize_youtube_candidate(raw_item)
    assert normalized is not None
    assert normalized["external_id"] == "dQw4w9WgXcQ"
    assert normalized["platform"] == "youtube"
    assert normalized["title"] == "Rick Astley - Never Gonna Give You Up (Official Music Video)"
    assert normalized["description"] == "The official video for Never Gonna Give You Up."
    assert normalized["channel_id"] == "UCuAXFkgsw1L7xaCfnd5JJOw"
    assert normalized["channel_name"] == "Rick Astley"
    assert normalized["thumbnail_url"] == "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg"
    assert normalized["duration_seconds"] == 213
    assert normalized["views"] == 1500000000
    assert normalized["likes"] == 17000000
    assert normalized["comments"] == 2500000
    assert normalized["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_normalize_payload_with_missing_optional_fields():
    """Verify conversion works smoothly when optional fields (statistics, description, thumbnails) are absent."""
    sparse_item = {
        "id": "sparse_yt_01",
        "snippet": {
            "title": "Minimal Podcast Episode",
        },
        "contentDetails": {},
        "statistics": {},
    }

    normalized = normalize_youtube_candidate(sparse_item)
    assert normalized is not None
    assert normalized["external_id"] == "sparse_yt_01"
    assert normalized["title"] == "Minimal Podcast Episode"
    assert normalized["description"] is None
    assert normalized["channel_id"] is None
    assert normalized["channel_name"] == "Unknown Channel"
    assert normalized["thumbnail_url"] is None
    assert normalized["duration_seconds"] == 0
    assert normalized["views"] == 0
    assert normalized["likes"] == 0
    assert normalized["comments"] == 0


def test_normalize_invalid_payload_returns_none():
    """Verify invalid payloads lacking video ID or wrong structure return None."""
    assert normalize_youtube_candidate({}) is None
    assert normalize_youtube_candidate({"snippet": {"title": "Missing ID"}}) is None
    assert normalize_youtube_candidate("not a dict") is None
