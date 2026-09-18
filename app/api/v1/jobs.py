"""Job inspection endpoints."""

from datetime import datetime
from typing import Annotated, Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.database.session import get_db
from app.domain.enums import JobStatus, JobType
from app.repositories.job_repository import JobRepository

router = APIRouter()


class JobResponse(BaseModel):
    """Detailed job status and execution diagnostics."""

    id: str
    project_id: Optional[str] = None
    job_type: JobType
    status: JobStatus
    idempotency_key: str
    retry_count: int
    max_retries: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None


@router.get("/{job_id}", response_model=JobResponse, summary="Get job execution status and diagnostics")
def get_job(job_id: str, session: Annotated[Session, Depends(get_db)]) -> JobResponse:
    """Retrieve execution state, failure codes, and result metadata for an idempotent job."""
    job = JobRepository.get_by_id(session, job_id)
    if not job:
        raise NotFoundError("Job", job_id)

    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type,
        status=job.status,
        idempotency_key=job.idempotency_key,
        retry_count=job.retry_count,
        max_retries=job.max_retries,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        error_code=job.error_code,
        error_message=job.error_message,
        metadata_json=job.metadata_json,
    )
