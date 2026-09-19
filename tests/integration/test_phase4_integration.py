"""Integration tests for Phase 4 Popularity persistence, human rights decisions, and audit events."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.errors import RightsAuthorizationError
from app.database.models.source import Source
from app.domain.enums import EvidenceStatus, LicenseType, ReviewerRole, RightsStatus, SourceClass, WorkflowState
from app.repositories.audit_repository import AuditRepository
from app.repositories.popularity_repository import PopularityRepository
from app.repositories.source_repository import SourceRepository
from app.services.popularity_service import PopularityService
from app.services.rights_service import RightsService


def test_mysql_popularity_score_persistence_and_invariance(mysql_session: Session):
    """PopularityService must persist score in MySQL and NEVER mutate rights or workflow state."""
    source = Source(
        platform="youtube",
        external_id="yt_p4_pop_01",
        title="Popularity Test Episode",
        url="https://youtube.com/watch?v=pop01",
        published_at=datetime.now(timezone.utc) - timedelta(days=3),
        views=200000,
        likes=12000,
        comments=650,
        duration_seconds=1800,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    # Calculate popularity score
    score_record = PopularityService.calculate_and_record(
        session=mysql_session,
        source_id=source.id,
    )

    # 1. Verify persistence in MySQL
    fetched = PopularityRepository.get_by_id(mysql_session, score_record.id)
    assert fetched is not None
    assert fetched.source_id == source.id
    assert fetched.final_score > 0.0
    assert fetched.algorithm_version == "popularity_v1"
    assert "Active components:" in fetched.rationale

    # 2. SAFETY INVARIANT: Popularity score NEVER changes rights status or workflow state!
    assert source.rights_status == RightsStatus.REVIEW_REQUIRED
    assert source.workflow_state == WorkflowState.DISCOVERED

    # 3. Verify audit event
    audit_events = AuditRepository.list_by_entity(mysql_session, "Source", source.id)
    actions = [e.action for e in audit_events]
    assert "POPULARITY_SCORE_CALCULATED" in actions


def test_mysql_human_rights_approval_transactional(mysql_session: Session):
    """Human review decision must transactionally update rights, source, and produce audit event."""
    source = Source(
        platform="youtube",
        external_id="yt_p4_rights_appr_01",
        title="Creator Interview",
        url="https://youtube.com/watch?v=appr01",
        published_at=datetime.now(timezone.utc),
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    record = RightsService.record_human_decision(
        session=mysql_session,
        source_id=source.id,
        decision=RightsStatus.APPROVED,
        evidence_status=EvidenceStatus.CREATIVE_COMMONS_VERIFIED,
        reviewer="elena_compliance",
        reviewer_role=ReviewerRole.COMPLIANCE_OFFICER.value,
        decision_reason="Verified CC-BY license and commercial suitability.",
        evidence_reference="https://youtube.com/watch?v=appr01/license_verified",
        attribution_required=True,
    )

    # Verification
    assert record.decision == RightsStatus.APPROVED
    assert record.evidence_status == EvidenceStatus.CREATIVE_COMMONS_VERIFIED
    assert source.rights_status == RightsStatus.APPROVED
    assert source.workflow_state == WorkflowState.RIGHTS_APPROVED

    # Verify audit event
    audit_events = AuditRepository.list_by_entity(mysql_session, "Source", source.id)
    actions = [e.action for e in audit_events]
    assert "RIGHTS_APPROVAL_GRANTED" in actions


def test_mysql_human_rights_rejection_transactional(mysql_session: Session):
    """Human rejection decision must transition state to RIGHTS_BLOCKED and audit."""
    source = Source(
        platform="youtube",
        external_id="yt_p4_rights_rej_01",
        title="Unlicensed Music Video",
        url="https://youtube.com/watch?v=rej01",
        published_at=datetime.now(timezone.utc),
        source_class=SourceClass.UNKNOWN,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    record = RightsService.record_human_decision(
        session=mysql_session,
        source_id=source.id,
        decision=RightsStatus.BLOCKED,
        evidence_status=EvidenceStatus.REJECTED,
        reviewer="marcus_legal",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
        decision_reason="Contains copyrighted music without commercial license.",
    )

    assert record.decision == RightsStatus.BLOCKED
    assert source.rights_status == RightsStatus.BLOCKED
    assert source.workflow_state == WorkflowState.RIGHTS_BLOCKED

    audit_events = AuditRepository.list_by_entity(mysql_session, "Source", source.id)
    actions = [e.action for e in audit_events]
    assert "RIGHTS_APPROVAL_REJECTED" in actions


def test_mysql_human_review_rejects_unauthorized_ai_reviewer(mysql_session: Session):
    """AI/automated reviewer attempting final rights decision must raise RightsAuthorizationError."""
    source = Source(
        platform="youtube",
        external_id="yt_p4_ai_attempt",
        title="Attempted AI Clearance",
        url="https://youtube.com/watch?v=ai01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    with pytest.raises(RightsAuthorizationError) as exc_info:
        RightsService.record_human_decision(
            session=mysql_session,
            source_id=source.id,
            decision=RightsStatus.APPROVED,
            evidence_status=EvidenceStatus.OWNED,
            reviewer="ai_rights_agent_v1",
            reviewer_role=ReviewerRole.AI_AGENT.value,
            decision_reason="AI evaluated copyright risk as low.",
        )
    assert "Unauthorized reviewer" in str(exc_info.value)
