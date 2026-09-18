"""Health and Readiness endpoints."""

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.config import settings
from app.database.session import check_database_connection

router = APIRouter(tags=["System Health"])


class HealthResponse(BaseModel):
    """Application liveness status."""

    status: str
    version: str


class ReadyResponse(BaseModel):
    """Application readiness status including dependency checks."""

    status: str
    database: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness probe: returns application status without external dependencies."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
    )


@router.get("/ready", response_model=ReadyResponse)
def readiness_check(response: Response) -> ReadyResponse:
    """Readiness probe: checks required database connectivity."""
    is_db_connected = check_database_connection()
    if not is_db_connected:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(
            status="not_ready",
            database="disconnected",
        )

    return ReadyResponse(
        status="ready",
        database="connected",
    )
