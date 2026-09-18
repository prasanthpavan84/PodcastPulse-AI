"""Job execution service with idempotency and retry policies."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.database.models.job import Job
from app.domain.enums import JobStatus, JobType
from app.repositories.job_repository import JobRepository

logger = get_logger("job_service")


class JobService:
    """Manages job lifecycles with strict idempotency and bounded retries."""

    @staticmethod
    def get_or_create_job(
        session: Session,
        job_type: JobType,
        idempotency_key: str,
        project_id: Optional[str] = None,
        max_retries: int = 3,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """Fetch existing job by idempotency key or initialize a new PENDING job."""
        existing = JobRepository.get_by_idempotency_key(session, idempotency_key)
        if existing:
            return existing

        job = Job(
            project_id=project_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            idempotency_key=idempotency_key,
            max_retries=max_retries,
            metadata_json=metadata_json,
        )
        JobRepository.save(session, job)
        logger.info("job_created", job_id=job.id, job_type=job_type.value, idempotency_key=idempotency_key)
        return job

    @staticmethod
    def start_job(session: Session, job_id: str) -> Job:
        """Mark job as RUNNING with started_at timestamp."""
        job = JobRepository.get_by_id(session, job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        job.status = JobStatus.RUNNING
        job.started_at = datetime.now(timezone.utc)
        JobRepository.save(session, job)
        logger.info("job_started", job_id=job.id, retry_count=job.retry_count)
        return job

    @staticmethod
    def complete_job(
        session: Session,
        job_id: str,
        result_metadata: Optional[Dict[str, Any]] = None,
    ) -> Job:
        """Mark job as COMPLETED and compute duration."""
        job = JobRepository.get_by_id(session, job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        now = datetime.now(timezone.utc)
        job.status = JobStatus.COMPLETED
        job.completed_at = now
        if job.started_at:
            job.duration_seconds = (now - job.started_at).total_seconds()

        if result_metadata:
            merged = dict(job.metadata_json or {})
            merged.update(result_metadata)
            job.metadata_json = merged
            from sqlalchemy.orm.attributes import flag_modified

            flag_modified(job, "metadata_json")

        JobRepository.save(session, job)
        logger.info("job_completed", job_id=job.id, duration_seconds=job.duration_seconds)
        return job

    @staticmethod
    def fail_job(
        session: Session,
        job_id: str,
        error_code: str,
        error_message: str,
        error_payload: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ) -> Job:
        """Record job failure, evaluate retry policy, and update state."""
        job = JobRepository.get_by_id(session, job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        now = datetime.now(timezone.utc)
        job.completed_at = now
        if job.started_at:
            job.duration_seconds = (now - job.started_at).total_seconds()

        job.error_code = error_code
        job.error_message = error_message
        job.error_payload = error_payload

        # Evaluate retry policy for transient failures
        if retryable and job.retry_count < job.max_retries:
            job.retry_count += 1
            job.status = JobStatus.RETRYING
            logger.warn(
                "job_scheduled_retry",
                job_id=job.id,
                retry_count=job.retry_count,
                max_retries=job.max_retries,
                error_code=error_code,
            )
        else:
            job.status = JobStatus.FAILED
            logger.error(
                "job_failed_terminal",
                job_id=job.id,
                error_code=error_code,
                error_message=error_message,
            )

        JobRepository.save(session, job)
        return job
