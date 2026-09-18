"""Explicit repository for Job execution entities."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.job import Job
from app.domain.enums import JobStatus


class JobRepository:
    """Persistence operations for idempotent execution jobs."""

    @staticmethod
    def get_by_id(session: Session, job_id: str) -> Optional[Job]:
        """Fetch job by UUID."""
        stmt = select(Job).where(Job.id == job_id)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_idempotency_key(session: Session, idempotency_key: str) -> Optional[Job]:
        """Fetch existing job by unique idempotency key."""
        stmt = select(Job).where(Job.idempotency_key == idempotency_key)
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def list_by_project(session: Session, project_id: str) -> List[Job]:
        """List all jobs associated with a project."""
        stmt = select(Job).where(Job.project_id == project_id).order_by(Job.created_at.desc())
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def list_active_jobs(session: Session, limit: int = 50) -> List[Job]:
        """List pending or running jobs."""
        stmt = (
            select(Job)
            .where(Job.status.in_([JobStatus.PENDING, JobStatus.RUNNING]))
            .order_by(Job.created_at.asc())
            .limit(limit)
        )
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def save(session: Session, job: Job) -> Job:
        """Insert or update a job record."""
        session.add(job)
        session.flush()
        return job
