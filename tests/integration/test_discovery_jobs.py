"""Integration tests for Job lifecycle and idempotency in discovery workflows."""

import pytest
from sqlalchemy.orm import Session

from app.adapters.mocks import MockYouTubeDiscovery
from app.core.errors import AppError, ErrorCode
from app.domain.enums import JobStatus, JobType
from app.repositories.job_repository import JobRepository
from app.services.discovery_service import DiscoveryService


def test_discovery_job_creation_and_completion_lifecycle(mysql_session: Session):
    """Verify discovery execution creates and completes a DISCOVERY_JOB with metadata."""
    idem_key = "discovery_job_lifecycle_test_01"
    adapter = MockYouTubeDiscovery()

    result = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter,
        topics=["Artificial Intelligence"],
        idempotency_key=idem_key,
    )

    job_id = result["job_id"]
    job = JobRepository.get_by_id(mysql_session, job_id)
    assert job is not None
    assert job.job_type == JobType.DISCOVERY_JOB
    assert job.status == JobStatus.COMPLETED
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.duration_seconds is not None
    assert job.metadata_json["discovered_count"] >= 1


def test_discovery_job_strict_idempotency(mysql_session: Session):
    """Verify repeated call with identical idempotency key returns existing job without re-executing."""
    idem_key = "discovery_strict_idempotency_key_999"
    adapter = MockYouTubeDiscovery()

    # First run
    res1 = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter,
        topics=["Robotics"],
        idempotency_key=idem_key,
    )

    # Second run with same key
    res2 = DiscoveryService.discover_youtube_candidates(
        session=mysql_session,
        adapter=adapter,
        topics=["Robotics"],
        idempotency_key=idem_key,
    )

    assert res1["job_id"] == res2["job_id"]
    assert res1["status"] == res2["status"]

    # Ensure only 1 job exists in database for this key
    fetched = JobRepository.get_by_idempotency_key(mysql_session, idem_key)
    assert fetched is not None
    assert fetched.id == res1["job_id"]


def test_discovery_job_failure_state_recording(mysql_session: Session):
    """Verify discovery job marks failure and records error diagnostics when adapter raises an exception."""
    idem_key = "discovery_job_failure_test_key"

    class FailingAdapter(MockYouTubeDiscovery):
        def search_candidates(self, *args, **kwargs):
            raise AppError(
                code=ErrorCode.EXTERNAL_SERVICE_ERROR,
                message="Simulated external API outage",
                status_code=502,
                retryable=True,
            )

    failing_adapter = FailingAdapter()

    with pytest.raises(AppError):
        DiscoveryService.discover_youtube_candidates(
            session=mysql_session,
            adapter=failing_adapter,
            topics=["FailTopic"],
            idempotency_key=idem_key,
        )

    job = JobRepository.get_by_idempotency_key(mysql_session, idem_key)
    assert job is not None
    assert job.status in (JobStatus.FAILED, JobStatus.RETRYING)
    assert job.error_code == ErrorCode.EXTERNAL_SERVICE_ERROR.value
    assert "Simulated external API outage" in job.error_message
