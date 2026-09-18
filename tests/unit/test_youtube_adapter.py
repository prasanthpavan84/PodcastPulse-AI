"""Unit tests for YouTubeAPIAdapter mocking HTTP interactions."""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.adapters.youtube import YouTubeAPIAdapter
from app.core.errors import AppError, ErrorCode


def test_missing_api_key_raises_configuration_error():
    """Verify adapter raises configuration error if no API key is provided."""
    adapter = YouTubeAPIAdapter(api_key=None)
    with pytest.raises(AppError) as exc_info:
        adapter.search_candidates(topics=["AI"])
    assert exc_info.value.code == ErrorCode.CONFIGURATION_ERROR
    assert exc_info.value.status_code == 500


def test_successful_search_and_hydration_flow():
    """Verify search followed by hydration returns normalized candidate metadata."""
    secret_key = "AIzaSyFakeSecretKeyForTestingOnly123"
    adapter = YouTubeAPIAdapter(api_key=secret_key)

    search_json = {
        "items": [
            {
                "id": {"kind": "youtube#video", "videoId": "vid_abc_123"},
                "snippet": {"title": "AI Revolution Video"},
            }
        ]
    }
    videos_json = {
        "items": [
            {
                "id": "vid_abc_123",
                "snippet": {
                    "title": "AI Revolution Video",
                    "description": "Deep dive into AI",
                    "channelId": "UC_channel_ai",
                    "channelTitle": "AI Channel",
                    "publishedAt": "2026-08-20T10:00:00Z",
                    "thumbnails": {"high": {"url": "https://img.youtube.com/vi/vid_abc_123/hqdefault.jpg"}},
                },
                "contentDetails": {"duration": "PT20M15S"},
                "statistics": {"viewCount": "50000", "likeCount": "2000", "commentCount": "150"},
            }
        ]
    }

    def _mock_get(url, params=None):
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 200
        mock_resp.raise_for_status.return_value = None
        if "search" in url:
            mock_resp.json.return_value = search_json
        else:
            mock_resp.json.return_value = videos_json
        return mock_resp

    with patch("httpx.Client.get", side_effect=_mock_get):
        candidates = adapter.search_candidates(topics=["AI Revolution"], min_views=10000)

    assert len(candidates) == 1
    c = candidates[0]
    assert c["external_id"] == "vid_abc_123"
    assert c["title"] == "AI Revolution Video"
    assert c["views"] == 50000
    assert c["duration_seconds"] == 1215


def test_empty_search_result_returns_empty_list():
    """Verify empty search results return an empty candidate list without executing video details request."""
    adapter = YouTubeAPIAdapter(api_key="fake_key")

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status.return_value = None
    mock_resp.json.return_value = {"items": []}

    with patch("httpx.Client.get", return_value=mock_resp) as mock_get:
        candidates = adapter.search_candidates(topics=["NonexistentTopic12345"])

    assert candidates == []
    assert mock_get.call_count == 1


def test_quota_exceeded_error_maps_to_429():
    """Verify YouTube API 403 quotaExceeded error maps to application error 429 without leaking secrets."""
    secret_key = "AIzaSySuperSecretKeyToSanitize"
    adapter = YouTubeAPIAdapter(api_key=secret_key)

    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 403
    mock_resp.json.return_value = {
        "error": {
            "errors": [{"reason": "quotaExceeded", "message": f"Quota exceeded for key {secret_key}"}],
            "message": f"Daily quota exceeded for key {secret_key}",
        }
    }
    mock_resp.text = f"Quota exceeded with key={secret_key}"

    http_error = httpx.HTTPStatusError(
        message="Client error '403 Forbidden'",
        request=MagicMock(),
        response=mock_resp,
    )

    with patch("httpx.Client.get", side_effect=http_error):
        with pytest.raises(AppError) as exc_info:
            adapter.search_candidates(topics=["Technology"])

    err = exc_info.value
    assert err.status_code == 429
    assert "quota exceeded" in err.message.lower()
    # Ensure secret is strictly sanitized
    assert secret_key not in err.message
    assert "***REDACTED***" in err.message


def test_timeout_error_maps_to_504():
    """Verify network or gateway timeout maps to 504 retryable AppError."""
    adapter = YouTubeAPIAdapter(api_key="fake_key")

    with patch("httpx.Client.get", side_effect=httpx.TimeoutException("Connection timed out")):
        with pytest.raises(AppError) as exc_info:
            adapter.search_candidates(topics=["Technology"])

    err = exc_info.value
    assert err.status_code == 504
    assert err.retryable is True


def test_secret_sanitization_removes_query_keys():
    """Verify _sanitize_text strips both raw key values and key= query params."""
    key = "AIzaSyTestKeyXYZ123456"
    adapter = YouTubeAPIAdapter(api_key=key)

    raw_text = f"Error calling https://www.googleapis.com/youtube/v3/search?part=snippet&key={key}&q=test"
    sanitized = adapter._sanitize_text(raw_text)

    assert key not in sanitized
    assert "key=***REDACTED***" in sanitized
