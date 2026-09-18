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
