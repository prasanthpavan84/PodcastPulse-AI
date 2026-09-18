"""YouTube discovery endpoints."""

from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.adapters.interfaces import YouTubeDiscovery
from app.adapters.youtube import YouTubeAPIAdapter
from app.core.errors import DomainValidationError
from app.core.logging import ctx_request_id, get_logger
from app.database.session import get_db
from app.domain.enums import JobStatus
from app.services.discovery_service import DiscoveryService

logger = get_logger("discovery_api")

router = APIRouter()


def get_youtube_adapter() -> YouTubeDiscovery:
    """Dependency provider for the YouTube discovery adapter."""
    return YouTubeAPIAdapter()


class YouTubeDiscoveryRequest(BaseModel):
    """Payload for initiating a YouTube content discovery search."""

    topics: List[str] = Field(default_factory=list, description="Topics to query on YouTube")
    keywords: Optional[List[str]] = Field(default=None, description="Keywords to refine topic queries")
    channels: Optional[List[str]] = Field(default=None, description="Target YouTube channel IDs")
    min_views: int = Field(default=10000, ge=0, description="Minimum view threshold for candidate ingestion")
    published_after_days: Optional[int] = Field(
        default=30, ge=1, le=3650, description="Lookback window in days (1-3650)"
    )
    published_after: Optional[datetime] = Field(default=None, description="ISO timestamp for earliest published date")
    published_before: Optional[datetime] = Field(default=None, description="ISO timestamp for latest published date")
    max_results: int = Field(default=25, ge=1, le=50, description="Maximum items per API query (1-50)")
    max_queries: Optional[int] = Field(default=5, ge=1, le=20, description="Maximum query requests per run")
    idempotency_key: Optional[str] = Field(default=None, description="Optional unique client idempotency key")

    @field_validator("topics", mode="after")
    @classmethod
    def clean_topics(cls, v: List[str]) -> List[str]:
        return [t.strip() for t in v if t.strip()]


class DiscoveredSourceItem(BaseModel):
    """Summary of a discovered or deduplicated video source."""

    source_id: str
    external_id: str
    title: str
    is_new: bool
    trend_score: Optional[float] = None
    workflow_state: str


class YouTubeDiscoveryResponse(BaseModel):
    """Structured response for a discovery run."""

    job_id: str
    status: JobStatus
    idempotency_key: str
    discovered_count: int
    new_sources_count: int
    existing_sources_count: int
    sources: List[DiscoveredSourceItem]


@router.post(
    "/youtube",
    response_model=YouTubeDiscoveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute YouTube content discovery and trend scoring",
)
def discover_youtube(
    request_data: YouTubeDiscoveryRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    adapter: Annotated[YouTubeDiscovery, Depends(get_youtube_adapter)],
) -> YouTubeDiscoveryResponse:
    """Execute bounded discovery search, normalize candidates, deduplicate sources, and calculate trend scores."""
    # Validation guard: ensure at least one criteria is provided
    has_topics = bool(request_data.topics)
    has_keywords = bool(request_data.keywords and any(k.strip() for k in request_data.keywords))
    has_channels = bool(request_data.channels and any(c.strip() for c in request_data.channels))

    if not has_topics and not has_keywords and not has_channels:
        raise DomainValidationError("At least one topic, keyword, or channel must be specified for discovery.")

    if request_data.published_after and request_data.published_before:
        if request_data.published_after > request_data.published_before:
            raise DomainValidationError("published_after cannot be later than published_before.")

    req_id = ctx_request_id.get() or request.headers.get("X-Request-ID")

    result = DiscoveryService.discover_youtube_candidates(
        session=session,
        adapter=adapter,
        topics=request_data.topics,
        keywords=request_data.keywords,
        channels=request_data.channels,
        min_views=request_data.min_views,
        published_after_days=request_data.published_after_days,
        published_after=request_data.published_after,
        published_before=request_data.published_before,
        max_results=request_data.max_results,
        max_queries=request_data.max_queries,
        idempotency_key=request_data.idempotency_key,
        request_id=req_id,
    )

    session.commit()

    return YouTubeDiscoveryResponse(
        job_id=result["job_id"],
        status=result["status"],
        idempotency_key=result["idempotency_key"],
        discovered_count=result["discovered_count"],
        new_sources_count=result["new_sources_count"],
        existing_sources_count=result["existing_sources_count"],
        sources=[DiscoveredSourceItem(**s) for s in result.get("sources", [])],
    )
