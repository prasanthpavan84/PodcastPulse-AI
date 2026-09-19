"""Unit tests for deterministic rights compliance, evidence validation, and authorization."""

from datetime import datetime, timedelta, timezone

from app.domain.enums import EvidenceStatus, LicenseType, ReviewerRole, RightsStatus, SourceClass
from app.domain.rights_rules import validate_evidence


def test_unknown_evidence_cannot_approve():
    """EvidenceStatus.UNKNOWN must never be approved."""
    res = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.UNKNOWN,
        decision=RightsStatus.APPROVED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
    )
    assert not res.is_valid
    assert "Cannot grant APPROVED rights when evidence status is UNKNOWN" in res.reason


def test_expired_evidence_cannot_approve():
    """Expired evidence cannot be approved."""
    now = datetime(2026, 9, 15, 12, 0, 0, tzinfo=timezone.utc)
    expired_date = now - timedelta(days=1)

    # 1. Past expiration date
    res = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.LICENSED,
        decision=RightsStatus.APPROVED,
        expires_at=expired_date,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
        reference_time=now,
    )
    assert not res.is_valid
    assert res.evidence_status == EvidenceStatus.EXPIRED

    # 2. Status set to EXPIRED
    res_status = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.EXPIRED,
        decision=RightsStatus.APPROVED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
    )
    assert not res_status.is_valid


def test_rejected_evidence_cannot_approve():
    """EvidenceStatus.REJECTED cannot be approved."""
    res = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.REJECTED,
        decision=RightsStatus.APPROVED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
    )
    assert not res.is_valid
    assert "Cannot grant APPROVED rights when evidence status is REJECTED" in res.reason


def test_creative_commons_label_alone_cannot_approve():
    """A Creative Commons claim without verified evidence reference cannot be approved."""
    res = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.UNKNOWN,  # Just unverified label
        decision=RightsStatus.APPROVED,
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY,
        reviewer="legal_lead",
        reviewer_role=ReviewerRole.RIGHTS_REVIEWER.value,
    )
    assert not res.is_valid

    # Even if client claims CREATIVE_COMMONS_VERIFIED, missing reference must fail
    res_no_ref = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.CREATIVE_COMMONS_VERIFIED,
        decision=RightsStatus.APPROVED,
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY,
        evidence_reference=None,
        reviewer="legal_lead",
        reviewer_role=ReviewerRole.RIGHTS_REVIEWER.value,
    )
    assert not res_no_ref.is_valid


def test_creative_commons_verified_evidence_approves():
    """Documented and verified Creative Commons evidence reference can be approved."""
    res = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.CREATIVE_COMMONS_VERIFIED,
        decision=RightsStatus.APPROVED,
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY,
        evidence_reference="https://creativecommons.org/licenses/by/4.0/legalcode",
        reviewer="legal_lead",
        reviewer_role=ReviewerRole.RIGHTS_REVIEWER.value,
    )
    assert res.is_valid
    assert res.evidence_status == EvidenceStatus.CREATIVE_COMMONS_VERIFIED


def test_human_authorization_boundary_rejects_ai_and_system():
    """AI/LLM agents or automated systems must be strictly prohibited from approving rights."""
    # Prohibited AI role
    res_ai = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.OWNED,
        decision=RightsStatus.APPROVED,
        reviewer="langgraph_agent_12",
        reviewer_role=ReviewerRole.AI_AGENT.value,
    )
    assert not res_ai.is_valid
    assert "Unauthorized reviewer" in res_ai.reason

    # Prohibited LLM role
    res_llm = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.OWNED,
        decision=RightsStatus.APPROVED,
        reviewer="ollama_llama3",
        reviewer_role=ReviewerRole.LLM.value,
    )
    assert not res_llm.is_valid

    # Prohibited automated system
    res_sys = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.OWNED,
        decision=RightsStatus.APPROVED,
        reviewer="system",
        reviewer_role=ReviewerRole.SYSTEM.value,
    )
    assert not res_sys.is_valid

    # Missing reviewer entirely
    res_none = validate_evidence(
        source_id="src_001",
        target_source_id="src_001",
        evidence_status=EvidenceStatus.OWNED,
        decision=RightsStatus.APPROVED,
        reviewer=None,
        reviewer_role=None,
    )
    assert not res_none.is_valid


def test_source_binding_rejects_mismatched_target():
    """Approval bound to Source A cannot authorize Source B."""
    res = validate_evidence(
        source_id="source_A",
        target_source_id="source_B",
        evidence_status=EvidenceStatus.OWNED,
        decision=RightsStatus.APPROVED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
    )
    assert not res.is_valid
    assert "Source mismatch" in res.reason


def test_project_binding_rejects_mismatched_target():
    """Approval bound to Project A cannot authorize Project B."""
    res = validate_evidence(
        source_id="source_A",
        target_source_id="source_A",
        project_id="project_A",
        target_project_id="project_B",
        evidence_status=EvidenceStatus.OWNED,
        decision=RightsStatus.APPROVED,
        reviewer="sarah_counsel",
        reviewer_role=ReviewerRole.LEGAL_COUNSEL.value,
    )
    assert not res.is_valid
    assert "Project mismatch" in res.reason
