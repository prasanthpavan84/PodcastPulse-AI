"""MySQL integration tests for RightsService, workflow gates, and audit event generation."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.errors import StateTransitionError
from app.database.models.source import Source
from app.domain.enums import LicenseType, RightsStatus, SourceClass, WorkflowState
from app.repositories.audit_repository import AuditRepository
from app.repositories.rights_repository import RightsRepository
from app.repositories.source_repository import SourceRepository
from app.services.rights_service import RightsService
from app.services.workflow_service import WorkflowService


def test_mysql_rights_evaluation_discovered_transition(mysql_session: Session):
    """Evaluating a DISCOVERED source must advance state canonically through RIGHTS_PENDING to RIGHTS_APPROVED."""
    source = Source(
        platform="youtube",
        external_id="yt_phase3_disc_01",
        title="Original Podcast Episode",
        url="https://youtube.com/watch?v=disc01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    record = RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.USER_OWNED,
        license_type=LicenseType.OWNED,
        evidence_reference="AFFIDAVIT-ORIGINAL-CREATOR-001",
    )

    assert record.decision == RightsStatus.APPROVED
    assert source.workflow_state == WorkflowState.RIGHTS_APPROVED
    assert source.rights_status == RightsStatus.APPROVED

    # Verify audit events
    audit_events = AuditRepository.list_by_entity(mysql_session, "Source", source.id)
    actions = [e.action for e in audit_events]

    assert "TRANSITION_DISCOVERED_TO_RIGHTS_PENDING" in actions
    assert "TRANSITION_RIGHTS_PENDING_TO_RIGHTS_APPROVED" in actions
    assert "RIGHTS_EVALUATION_APPROVED" in actions

    # Verify rights record retrieval by id
    fetched = RightsRepository.get_by_id(mysql_session, record.id)
    assert fetched is not None
    assert fetched.source_id == source.id


def test_mysql_rights_evaluation_blocked_and_gate_enforcement(mysql_session: Session):
    """Blocked content must be gated and prevented from entering TRANSCRIBING."""
    source = Source(
        platform="youtube",
        external_id="yt_phase3_nd_block",
        title="No Derivatives Song",
        url="https://youtube.com/watch?v=ndblock",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    record = RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY_ND,
        evidence_reference="https://creativecommons.org/licenses/by-nd/4.0/",
    )

    assert record.decision == RightsStatus.BLOCKED
    assert source.workflow_state == WorkflowState.RIGHTS_BLOCKED
    assert source.rights_status == RightsStatus.BLOCKED

    # Hard Gate Check: BLOCKED cannot transition to TRANSCRIBING
    with pytest.raises(StateTransitionError) as exc_info:
        WorkflowService.transition_source(
            session=mysql_session,
            source_id=source.id,
            requested_state=WorkflowState.TRANSCRIBING,
        )
    assert "BLOCKED" in str(exc_info.value)


def test_mysql_rights_review_required_cannot_reach_transcribing(mysql_session: Session):
    """Sources with REVIEW_REQUIRED status cannot transition to TRANSCRIBING."""
    source = Source(
        platform="youtube",
        external_id="yt_phase3_unknown_01",
        title="Unverified Public Video",
        url="https://youtube.com/watch?v=unv01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    record = RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.UNKNOWN,
        license_type=LicenseType.STANDARD_YOUTUBE,
    )

    assert record.decision == RightsStatus.REVIEW_REQUIRED
    assert source.workflow_state == WorkflowState.RIGHTS_PENDING
    assert source.rights_status == RightsStatus.REVIEW_REQUIRED

    with pytest.raises(StateTransitionError) as exc_info:
        WorkflowService.transition_source(
            session=mysql_session,
            source_id=source.id,
            requested_state=WorkflowState.TRANSCRIBING,
        )
    assert "Rights gate check failed" in str(exc_info.value)


def test_mysql_rights_reevaluation_from_blocked_to_approved(mysql_session: Session):
    """Blocked source can be re-evaluated and cleared upon receiving valid commercial evidence."""
    source = Source(
        platform="youtube",
        external_id="yt_phase3_reval_01",
        title="Licensed Music Track",
        url="https://youtube.com/watch?v=lic01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    # 1. Initial evaluation blocks due to missing commercial agreement
    RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=False,
        modification_allowed=True,
        evidence_reference="PENDING-INVOICE",
    )
    assert source.workflow_state == WorkflowState.RIGHTS_BLOCKED

    # 2. Re-evaluate with valid contract and clearance
    record2 = RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=True,
        attribution_required=False,
        evidence_reference="CLEARED-INV-9999",
        reviewer="legal_counsel",
    )

    assert record2.decision == RightsStatus.APPROVED
    assert source.workflow_state == WorkflowState.RIGHTS_APPROVED
    assert source.rights_status == RightsStatus.APPROVED

    # Now transition to TRANSCRIBING succeeds
    next_state = WorkflowService.transition_source(
        session=mysql_session,
        source_id=source.id,
        requested_state=WorkflowState.TRANSCRIBING,
        actor="orchestrator",
    )
    assert next_state == WorkflowState.TRANSCRIBING


def test_mysql_secret_redaction_in_audit_event(mysql_session: Session):
    """Audit payloads must automatically redact secrets and authorization tokens."""
    source = Source(
        platform="youtube",
        external_id="yt_phase3_audit_sec",
        title="Audit Security Test",
        url="https://youtube.com/watch?v=sec01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    event = AuditRepository.record_event(
        session=mysql_session,
        actor="sec_tester",
        action="TEST_ACTION",
        entity_type="Source",
        entity_id=source.id,
        payload={
            "api_key": "AIzaSySecret123456789",
            "auth_token": "Bearer supersecretjwttoken",
            "safe_metadata": "public_source",
        },
    )

    assert event.payload["api_key"] == "***REDACTED***"
    assert event.payload["auth_token"] == "***REDACTED***"
    assert event.payload["safe_metadata"] == "public_source"
