"""Integration tests running against the dedicated MySQL 8 test database."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import StateTransitionError
from app.database.models import Source
from app.domain.enums import (
    JobStatus,
    JobType,
    LicenseType,
    RightsStatus,
    SourceClass,
    WorkflowState,
)
from app.repositories import AuditRepository, SourceRepository
from app.services import JobService, RightsService, WorkflowService


def test_mysql_source_crud_and_indexes(mysql_session: Session):
    """Test Source entity persistence, UUID generation, and lookup by external_id on MySQL 8."""
    source = Source(
        platform="youtube",
        external_id="yt_test_101",
        title="Test Podcast Episode 101",
        url="https://youtube.com/watch?v=yt_test_101",
        published_at=datetime.now(timezone.utc),
        duration_seconds=1800,
        views=50000,
        workflow_state=WorkflowState.DISCOVERED,
    )
    SourceRepository.save(mysql_session, source)

    # Verify lookup by UUID
    fetched = SourceRepository.get_by_id(mysql_session, source.id)
    assert fetched is not None
    assert fetched.external_id == "yt_test_101"
    assert len(fetched.id) == 36  # UUID length

    # Verify lookup by external_id index
    by_ext = SourceRepository.get_by_external_id(mysql_session, "yt_test_101")
    assert by_ext is not None
    assert by_ext.id == source.id


def test_mysql_unique_constraint_enforcement(mysql_session: Session):
    """Verify MySQL 8 enforces relational unique constraints on external_id."""
    source1 = Source(
        platform="youtube",
        external_id="duplicate_id_test",
        title="Source 1",
        url="https://youtube.com/watch?v=1",
        published_at=datetime.now(timezone.utc),
    )
    SourceRepository.save(mysql_session, source1)
    mysql_session.flush()

    source2 = Source(
        platform="youtube",
        external_id="duplicate_id_test",
        title="Source 2",
        url="https://youtube.com/watch?v=2",
        published_at=datetime.now(timezone.utc),
    )
    mysql_session.add(source2)
    with pytest.raises(IntegrityError):
        mysql_session.flush()
    mysql_session.rollback()


def test_mysql_transactional_workflow_transition_creates_audit_event(mysql_session: Session):
    """Verify WorkflowService mutates state and creates an AuditEvent transactionally in MySQL 8."""
    source = Source(
        platform="youtube",
        external_id="yt_audit_test",
        title="Audit Test Episode",
        url="https://youtube.com/watch?v=audit",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
    )
    SourceRepository.save(mysql_session, source)

    # Transition to RIGHTS_PENDING
    new_state = WorkflowService.transition_source(
        session=mysql_session,
        source_id=source.id,
        requested_state=WorkflowState.RIGHTS_PENDING,
        actor="test_runner",
        reason="Initiating copyright inspection",
        request_id="req-9999",
    )
    assert new_state == WorkflowState.RIGHTS_PENDING

    # Verify audit record in database
    audit_events = AuditRepository.list_by_entity(mysql_session, "Source", source.id)
    assert len(audit_events) == 1
    event = audit_events[0]
    assert event.previous_state == WorkflowState.DISCOVERED.value
    assert event.new_state == WorkflowState.RIGHTS_PENDING.value
    assert event.actor == "test_runner"
    assert event.request_id == "req-9999"
    assert event.payload.get("reason") == "Initiating copyright inspection"


def test_mysql_job_idempotency_and_lifecycle(mysql_session: Session):
    """Verify JobService handles idempotency keys and retry increments on MySQL 8."""
    idem_key = "transcription_job_source_xyz_v1"

    # First call creates the job
    job1 = JobService.get_or_create_job(
        session=mysql_session,
        job_type=JobType.TRANSCRIPTION_JOB,
        idempotency_key=idem_key,
        max_retries=2,
    )
    assert job1.status == JobStatus.PENDING

    # Second call with same idempotency key returns existing job without duplication
    job2 = JobService.get_or_create_job(
        session=mysql_session,
        job_type=JobType.TRANSCRIPTION_JOB,
        idempotency_key=idem_key,
    )
    assert job1.id == job2.id

    # Start job
    JobService.start_job(mysql_session, job1.id)
    assert job1.status == JobStatus.RUNNING
    assert job1.started_at is not None

    # Transient failure triggers retry
    JobService.fail_job(
        session=mysql_session,
        job_id=job1.id,
        error_code="TRANSIENT_TIMEOUT",
        error_message="Connection timed out",
        retryable=True,
    )
    assert job1.status == JobStatus.RETRYING
    assert job1.retry_count == 1

    # Complete job
    JobService.complete_job(mysql_session, job1.id, result_metadata={"segments": 42})
    assert job1.status == JobStatus.COMPLETED
    assert job1.metadata_json.get("segments") == 42


def test_mysql_rights_service_evaluation_and_blocking(mysql_session: Session):
    """Verify RightsService blocks unauthorized sources and prevents downstream processing."""
    source = Source(
        platform="youtube",
        external_id="yt_cc_nd_test",
        title="NoDerivatives Episode",
        url="https://youtube.com/watch?v=nd",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.RIGHTS_PENDING,
    )
    SourceRepository.save(mysql_session, source)

    # Evaluate CC_BY_ND source
    record = RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY_ND,
        evidence_reference="https://creativecommons.org/licenses/by-nd/4.0/",
    )
    assert record.decision == RightsStatus.BLOCKED
    assert source.workflow_state == WorkflowState.RIGHTS_BLOCKED

    # Attempting to transition blocked source to TRANSCRIBING must fail
    with pytest.raises(StateTransitionError):
        WorkflowService.transition_source(
            session=mysql_session,
            source_id=source.id,
            requested_state=WorkflowState.TRANSCRIBING,
        )
