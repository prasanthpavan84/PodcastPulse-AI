"""Unit tests for deterministic rights rules (Pure Domain)."""

from app.domain.enums import LicenseType, RightsStatus, SourceClass
from app.domain.rights_rules import evaluate_rights


def test_user_owned_content_is_automatically_approved():
    """Creator's own material requires no third-party clearance."""
    res = evaluate_rights(
        source_class=SourceClass.USER_OWNED,
        license_type=LicenseType.OWNED,
    )
    assert res.status == RightsStatus.APPROVED
    assert res.requires_human_review is False


def test_commercial_license_requires_evidence_reference():
    """Commercial license without contract reference must prompt review."""
    res = evaluate_rights(
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=True,
        evidence_reference=None,
    )
    assert res.status == RightsStatus.REVIEW_REQUIRED
    assert res.requires_human_review is True

    # With evidence reference, it is approved
    res_valid = evaluate_rights(
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=True,
        evidence_reference="INVOICE-COM-9921",
    )
    assert res_valid.status == RightsStatus.APPROVED


def test_creative_commons_non_commercial_is_blocked():
    """CC-BY-NC source must be blocked for commercial short production."""
    res = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY_NC,
        evidence_reference="https://creativecommons.org/licenses/by-nc/4.0/",
    )
    assert res.status == RightsStatus.BLOCKED


def test_creative_commons_no_derivatives_is_blocked():
    """CC-BY-ND source must be blocked because short transformation is a derivative work."""
    res = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY_ND,
        evidence_reference="https://creativecommons.org/licenses/by-nd/4.0/",
    )
    assert res.status == RightsStatus.BLOCKED


def test_creative_commons_compatible_is_conditional_on_attribution():
    """CC-BY with valid evidence is CONDITIONAL because attribution is legally required."""
    res = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY,
        attribution_required=True,
        evidence_reference="https://youtube.com/watch?v=123 (Creative Commons marked)",
    )
    assert res.status == RightsStatus.CONDITIONAL
    assert res.attribution_required is True


def test_unknown_rights_never_auto_approved():
    """Hard Rule: Unknown rights must NEVER be automatically approved."""
    res = evaluate_rights(
        source_class=SourceClass.UNKNOWN,
        license_type=LicenseType.UNKNOWN,
    )
    assert res.status in {RightsStatus.REVIEW_REQUIRED, RightsStatus.BLOCKED}
    assert res.status != RightsStatus.APPROVED
    assert res.requires_human_review is True


def test_legacy_class_code_mapping():
    """Verify backward compatibility from CLASS_A-E to readable names."""
    assert SourceClass.from_legacy_code("CLASS_A") == SourceClass.USER_OWNED
    assert SourceClass.from_legacy_code("CLASS_B") == SourceClass.COMMERCIAL_LICENSE
    assert SourceClass.from_legacy_code("CLASS_C") == SourceClass.CREATIVE_COMMONS
    assert SourceClass.from_legacy_code("CLASS_D") == SourceClass.PERMISSION_BASED
    assert SourceClass.from_legacy_code("CLASS_E") == SourceClass.UNKNOWN
    assert SourceClass.from_legacy_code("INVALID") == SourceClass.UNKNOWN


def test_user_owned_with_explicit_evidence():
    """User-owned material with explicit evidence records reference."""
    res = evaluate_rights(
        source_class=SourceClass.USER_OWNED,
        license_type=LicenseType.OWNED,
        evidence_reference="DOCS/ORIGINAL_CREATOR_AFFIDAVIT.PDF",
    )
    assert res.status == RightsStatus.APPROVED
    assert "ORIGINAL_CREATOR_AFFIDAVIT" in res.decision_reason
    assert not res.requires_human_review


def test_commercial_license_incompatibilities():
    """Commercial license with commercial_use=False or modification_allowed=False must be BLOCKED."""
    # Disallows commercial use
    res_no_comm = evaluate_rights(
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=False,
        modification_allowed=True,
        evidence_reference="INV-1234",
    )
    assert res_no_comm.status == RightsStatus.BLOCKED
    assert res_no_comm.requires_human_review is True

    # Disallows modification
    res_no_mod = evaluate_rights(
        source_class=SourceClass.COMMERCIAL_LICENSE,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=False,
        evidence_reference="INV-1234",
    )
    assert res_no_mod.status == RightsStatus.BLOCKED
    assert res_no_mod.requires_human_review is True


def test_creative_commons_cc0_policy():
    """CC0 dedication allows reuse without attribution by default."""
    res_unconditional = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC0,
        attribution_required=False,
        evidence_reference="https://creativecommons.org/publicdomain/zero/1.0/",
    )
    assert res_unconditional.status == RightsStatus.APPROVED
    assert not res_unconditional.attribution_required
    assert res_unconditional.conditions == ()

    # If policy requires attribution condition
    res_conditional = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC0,
        attribution_required=True,
        evidence_reference="https://creativecommons.org/publicdomain/zero/1.0/",
    )
    assert res_conditional.status == RightsStatus.CONDITIONAL
    assert "attribution_required" in res_conditional.conditions


def test_creative_commons_cc_by_sa_conditions():
    """CC-BY-SA requires both attribution and share-alike conditions."""
    res = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY_SA,
        evidence_reference="https://creativecommons.org/licenses/by-sa/4.0/",
        attribution_required=True,
    )
    assert res.status == RightsStatus.CONDITIONAL
    assert "attribution_required" in res.conditions
    assert "share_alike_required" in res.conditions
    assert not res.requires_human_review


def test_creative_commons_missing_evidence():
    """Creative Commons without evidence requires human review."""
    res = evaluate_rights(
        source_class=SourceClass.CREATIVE_COMMONS,
        license_type=LicenseType.CC_BY,
        evidence_reference=None,
    )
    assert res.status == RightsStatus.REVIEW_REQUIRED
    assert res.requires_human_review is True


def test_permission_based_evaluation_matrix():
    """Permission-based material requires both evidence reference and reviewer."""
    # Missing reviewer
    res_no_reviewer = evaluate_rights(
        source_class=SourceClass.PERMISSION_BASED,
        license_type=LicenseType.COMMERCIAL,
        evidence_reference="AGREEMENT-PDF-441",
        reviewer=None,
    )
    assert res_no_reviewer.status == RightsStatus.REVIEW_REQUIRED

    # Missing evidence
    res_no_evidence = evaluate_rights(
        source_class=SourceClass.PERMISSION_BASED,
        license_type=LicenseType.COMMERCIAL,
        evidence_reference=None,
        reviewer="legal_lead",
    )
    assert res_no_evidence.status == RightsStatus.REVIEW_REQUIRED

    # Prohibits commercial use
    res_no_comm = evaluate_rights(
        source_class=SourceClass.PERMISSION_BASED,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=False,
        modification_allowed=True,
        evidence_reference="AGREEMENT-PDF-441",
        reviewer="legal_lead",
    )
    assert res_no_comm.status == RightsStatus.BLOCKED

    # Valid with attribution
    res_valid_attr = evaluate_rights(
        source_class=SourceClass.PERMISSION_BASED,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=True,
        attribution_required=True,
        evidence_reference="AGREEMENT-PDF-441",
        reviewer="legal_lead",
    )
    assert res_valid_attr.status == RightsStatus.CONDITIONAL
    assert "attribution_required" in res_valid_attr.conditions

    # Valid without attribution
    res_valid_no_attr = evaluate_rights(
        source_class=SourceClass.PERMISSION_BASED,
        license_type=LicenseType.COMMERCIAL,
        commercial_use=True,
        modification_allowed=True,
        attribution_required=False,
        evidence_reference="AGREEMENT-PDF-441",
        reviewer="legal_lead",
    )
    assert res_valid_no_attr.status == RightsStatus.APPROVED
    assert res_valid_no_attr.conditions == ()
    assert "legal_lead" in res_valid_no_attr.decision_reason
