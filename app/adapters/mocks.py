"""Explicit mock implementations of execution adapters for unit testing and local development.

All outputs are clearly identified as MOCK in accordance with anti-fake engineering rules.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from app.adapters.interfaces import (
    LLMProvider,
    MediaAcquisition,
    MediaRenderer,
    TTSProvider,
    YouTubeDiscovery,
)


class MockLLMProvider(LLMProvider):
    """MOCK LLM adapter: Returns canned structured JSON responses for testing."""

    is_mock: bool = True

    def __init__(self, canned_response: Optional[str] = None):
        self.canned_response = canned_response or '{"status": "MOCK_OK", "result": "Generated from MockLLMProvider"}'

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        return self.canned_response


class MockMediaRenderer(MediaRenderer):
    """MOCK MediaRenderer adapter: Simulates FFmpeg rendering without spawning processes."""

    is_mock: bool = True

    def render_short(
        self,
        scene_manifest: Dict[str, Any],
        output_path: str,
        resolution: str = "1080x1920",
        fps: int = 30,
    ) -> Dict[str, Any]:
        return {
            "mode": "MOCK",
            "output_path": output_path,
            "resolution": resolution,
            "fps": fps,
            "duration_seconds": 45.0,
            "rendered": False,
        }


class MockTTSProvider(TTSProvider):
    """MOCK TTS adapter: Simulates voice generation without model inference."""

    is_mock: bool = True

    def synthesize(
        self,
        text: str,
        output_wav_path: str,
        voice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "mode": "MOCK",
            "output_path": output_wav_path,
            "duration_seconds": 30.0,
            "synthesized": False,
        }


class MockYouTubeDiscovery(YouTubeDiscovery):
    """MOCK YouTube adapter: Returns deterministic synthetic search candidates."""

    is_mock: bool = True

    def __init__(self, canned_candidates: Optional[List[Dict[str, Any]]] = None):
        self.canned_candidates = canned_candidates

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
        if self.canned_candidates is not None:
            return self.canned_candidates

        return [
            {
                "mode": "MOCK",
                "external_id": "mock_yt_001",
                "platform": "youtube",
                "title": f"MOCK: Discussion on {topics[0] if topics else 'AI'}",
                "description": "A comprehensive synthetic discussion on technology trends.",
                "channel_id": channels[0] if channels else "UC_mock_channel_101",
                "channel_name": "AI Insights Podcast",
                "thumbnail_url": "https://img.youtube.com/vi/mock_yt_001/hqdefault.jpg",
                "views": 250000,
                "likes": 12000,
                "comments": 850,
                "duration_seconds": 3600,
                "url": "https://www.youtube.com/watch?v=mock_yt_001",
                "published_at": "2026-09-01T12:00:00Z",
            }
        ]


class MockMediaAcquisition(MediaAcquisition):
    """MOCK Media acquisition adapter: Simulates download without network traffic."""

    is_mock: bool = True

    def acquire_audio(self, source_url: str, destination_path: str) -> str:
        return f"MOCK_DOWNLOADED_TO:{destination_path}"
