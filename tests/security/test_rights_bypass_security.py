"""Security and bypass tests proving rights safety gates cannot be bypassed."""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError, StateTransitionError
from app.database.models.project import Project
from app.database.models.source import Source
from app.domain.enums import EvidenceStatus, LicenseType, ReviewerRole, RightsStatus, SourceClass, WorkflowState
from app.repositories.project_repository import ProjectRepository
from app.repositories.source_repository import SourceRepository
from app.services.popularity_service import PopularityService
from app.services.rights_service import RightsService
from app.services.workflow_service import WorkflowService


def test_popularity_bypass_fails(mysql_session: Session):
    """Popularity score = 100 with rights = REVIEW_REQUIRED must fail the downstream processing gate."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_viral_unapproved",
        title="Viral Video With High Popularity",
        url="https://youtube.com/watch?v=viral01",
        published_at=datetime.now(timezone.utc) - timedelta(hours=5),
        views=5000000,
        likes=300000,
        comments=25000,
        duration_seconds=1800,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    score_rec = PopularityService.calculate_and_record(mysql_session, source.id)
    assert score_rec.final_score >= 85.0

    # Downstream rights gate MUST block transition to TRANSCRIBING
    with pytest.raises(StateTransitionError) as exc_info:
        WorkflowService.transition_source(
            session=mysql_session,
            source_id=source.id,
            requested_state=WorkflowState.TRANSCRIBING,
        )
    assert "Rights gate check failed" in str(exc_info.value)


def test_popularity_zero_does_not_invalidate_approved_rights(mysql_session: Session):
    """Popularity score = 0 does not invalidate an approved source's rights."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_low_pop_approved",
        title="Niche Creator Interview",
        url="https://youtube.com/watch?v=niche01",
        published_at=datetime.now(timezone.utc) - timedelta(days=200),
        views=10,
        likes=0,
        comments=0,
        duration_seconds=1800,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    # Human approves rights
    RightsService.record_human_decision(
        session=mysql_session,
        source_id=source.id,
        decision=RightsStatus.APPROVED,
        evidence_status=EvidenceStatus.OWNED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
        decision_reason="Verified owner affidavit.",
    )

    # Popularity scores very low
    score_rec = PopularityService.calculate_and_record(mysql_session, source.id)
    assert score_rec.final_score < 30.0

    # Downstream processing MUST still succeed
    next_state = WorkflowService.transition_source(
        session=mysql_session,
        source_id=source.id,
        requested_state=WorkflowState.TRANSCRIBING,
    )
    assert next_state == WorkflowState.TRANSCRIBING


def test_unknown_rights_cannot_approve(mysql_session: Session):
    """Evidence status UNKNOWN cannot be approved by human review."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_unknown",
        title="Unknown Source",
        url="https://youtube.com/watch?v=unk01",
        published_at=datetime.now(timezone.utc),
        source_class=SourceClass.UNKNOWN,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    with pytest.raises(DomainValidationError) as exc_info:
        RightsService.record_human_decision(
            session=mysql_session,
            source_id=source.id,
            decision=RightsStatus.APPROVED,
            evidence_status=EvidenceStatus.UNKNOWN,
            reviewer="sarah_counsel",
            reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
            decision_reason="Attempted approval without evidence.",
        )
    assert "Cannot grant APPROVED rights when evidence status is UNKNOWN" in str(exc_info.value)


def test_expired_evidence_cannot_process(mysql_session: Session):
    """Evidence status EXPIRED cannot be approved or processed downstream."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_expired",
        title="Expired License Source",
        url="https://youtube.com/watch?v=exp01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    with pytest.raises(DomainValidationError):
        RightsService.record_human_decision(
            session=mysql_session,
            source_id=source.id,
            decision=RightsStatus.APPROVED,
            evidence_status=EvidenceStatus.EXPIRED,
            reviewer="sarah_counsel",
            reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
            decision_reason="Attempted approval on expired evidence.",
        )


def test_rejected_evidence_cannot_process(mysql_session: Session):
    """Evidence status REJECTED cannot be approved or processed downstream."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_rejected",
        title="Rejected Source",
        url="https://youtube.com/watch?v=rej01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    with pytest.raises(DomainValidationError):
        RightsService.record_human_decision(
            session=mysql_session,
            source_id=source.id,
            decision=RightsStatus.APPROVED,
            evidence_status=EvidenceStatus.REJECTED,
            reviewer="sarah_counsel",
            reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
            decision_reason="Attempted approval on rejected evidence.",
        )


def test_creative_commons_without_verification_blocked(mysql_session: Session):
    """Creative Commons label without verified evidence reference cannot be approved."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_cc_unverified",
        title="Unverified CC Source",
        url="https://youtube.com/watch?v=cc01",
        published_at=datetime.now(timezone.utc),
        source_class=SourceClass.CREATIVE_COMMONS,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    with pytest.raises(DomainValidationError) as exc_info:
        RightsService.record_human_decision(
            session=mysql_session,
            source_id=source.id,
            decision=RightsStatus.APPROVED,
            evidence_status=EvidenceStatus.CREATIVE_COMMONS_VERIFIED,
            evidence_reference=None,  # Missing evidence reference!
            reviewer="sarah_counsel",
            reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
            decision_reason="Attempting CC approval without verification proof.",
        )
    assert "verification requires documented evidence reference" in str(exc_info.value).lower()


def test_stale_approval_license_expired_today_blocks_processing(mysql_session: Session):
    """Approved yesterday, license expired today -> processing gate must fail."""
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    # License expired 1 hour ago
    expired_time = datetime.now(timezone.utc) - timedelta(hours=1)

    source = Source(
        platform="youtube",
        external_id="yt_sec_stale_exp",
        title="Stale License Source",
        url="https://youtube.com/watch?v=stale01",
        published_at=yesterday,
        source_class=SourceClass.COMMERCIAL_LICENSE,
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    # Approve with future expiration that has now passed
    # Directly set record with past expiration to simulate passage of time
    record = RightsService.evaluate_and_record(
        session=mysql_session,
        source_id=source.id,
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=True,
        evidence_reference="CONTRACT-EXP-101",
        reviewer="legal_lead",
    )
    # Manually backdate expiration to simulate expiration after approval
    record.expires_at = expired_time
    record.evidence_status = EvidenceStatus.LICENSED
    record.decision = RightsStatus.APPROVED
    source.rights_status = RightsStatus.APPROVED
    source.workflow_state = WorkflowState.RIGHTS_APPROVED
    mysql_session.flush()

    # Attempt downstream processing: MUST FAIL due to stale/expired evidence
    with pytest.raises(StateTransitionError) as exc_info:
        WorkflowService.transition_source(
            session=mysql_session,
            source_id=source.id,
            requested_state=WorkflowState.TRANSCRIBING,
        )
    assert "Evidence expired" in str(exc_info.value)


def test_source_mismatch_blocks_processing(mysql_session: Session):
    """Rights approved for Source A cannot authorize Source B."""
    source_a = Source(
        platform="youtube",
        external_id="yt_sec_src_a",
        title="Source A",
        url="https://youtube.com/watch?v=srcA",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source_a)

    RightsService.record_human_decision(
        session=mysql_session,
        source_id=source_a.id,
        decision=RightsStatus.APPROVED,
        evidence_status=EvidenceStatus.OWNED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
        decision_reason="Approved Source A.",
    )

    # Attempt to validate rights gate for Source A using target Source B
    with pytest.raises(Exception) as exc_info:
        RightsService.validate_rights_gate(
            session=mysql_session,
            source_id=source_a.id,
            target_source_id="source_b_id_different",
        )
    assert "Source mismatch" in str(exc_info.value)


def test_project_mismatch_blocks_processing(mysql_session: Session):
    """Rights tied to Project A cannot authorize Project B."""
    source = Source(
        platform="youtube",
        external_id="yt_sec_proj_mismatch",
        title="Project Source",
        url="https://youtube.com/watch?v=proj01",
        published_at=datetime.now(timezone.utc),
        workflow_state=WorkflowState.DISCOVERED,
        rights_status=RightsStatus.REVIEW_REQUIRED,
    )
    SourceRepository.save(mysql_session, source)

    proj_a = Project(
        source_id=source.id,
        title="Project A",
        state=WorkflowState.DISCOVERED,
    )
    proj_b = Project(
        source_id=source.id,
        title="Project B",
        state=WorkflowState.DISCOVERED,
    )
    ProjectRepository.save(mysql_session, proj_a)
    ProjectRepository.save(mysql_session, proj_b)

    # Human approves rights strictly bound to Project A
    RightsService.record_human_decision(
        session=mysql_session,
        source_id=source.id,
        decision=RightsStatus.APPROVED,
        evidence_status=EvidenceStatus.OWNED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
        decision_reason="Approved strictly for Project A.",
        project_id=proj_a.id,
    )

    # Transition Project B to media processing state (e.g. TRANSCRIBING) -> MUST FAIL
    with pytest.raises(StateTransitionError) as exc_info:
        WorkflowService.transition_project(
            session=mysql_session,
            project_id=proj_b.id,
            requested_state=WorkflowState.TRANSCRIBING,
        )
    assert "Project mismatch" in str(exc_info.value)
