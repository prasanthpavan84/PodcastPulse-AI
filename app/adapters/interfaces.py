"""Abstract provider interfaces for external services and execution adapters.

Ensures domain and application services remain strictly decoupled from third-party tools.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    """Abstract interface for large language model inference."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Execute text completion and return raw response string."""
        pass


class MediaRenderer(ABC):
    """Abstract interface for FFmpeg/video rendering execution."""

    @abstractmethod
    def render_short(
        self,
        scene_manifest: Dict[str, Any],
        output_path: str,
        resolution: str = "1080x1920",
        fps: int = 30,
    ) -> Dict[str, Any]:
        """Execute video render and return render metadata."""
        pass


class TTSProvider(ABC):
    """Abstract interface for local text-to-speech synthesis."""

    @abstractmethod
    def synthesize(
        self,
        text: str,
        output_wav_path: str,
        voice_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Synthesize speech audio file and return metadata."""
        pass


class YouTubeDiscovery(ABC):
    """Abstract interface for YouTube discovery operations."""

    @abstractmethod
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
        """Query external candidate videos."""
        pass


class MediaAcquisition(ABC):
    """Abstract interface for downloading/acquiring source media."""

    @abstractmethod
    def acquire_audio(self, source_url: str, destination_path: str) -> str:
        """Download or extract audio stream to local destination."""
        pass
