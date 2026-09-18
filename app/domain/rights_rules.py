"""Deterministic, evidence-based content rights evaluation rules.

Pure domain module: zero external framework dependencies.
"""

from dataclasses import dataclass
from typing import Optional

from app.domain.enums import LicenseType, RightsStatus, SourceClass


@dataclass(frozen=True)
class RightsEvaluationResult:
    """Outcome of deterministic rights evaluation."""

    status: RightsStatus
    decision_reason: str
    requires_human_review: bool
    attribution_required: bool
    conditions: tuple[str, ...] = ()
    ruleset_version: str = "1.0.0"


def evaluate_rights(
    source_class: SourceClass,
    license_type: LicenseType,
    commercial_use: bool = False,
    modification_allowed: bool = False,
    attribution_required: bool = True,
    evidence_reference: Optional[str] = None,
    reviewer: Optional[str] = None,
) -> RightsEvaluationResult:
    """Evaluate source reuse permissions deterministically.

    HARD RULES:
    1. Unknown rights NEVER become approved automatically.
    2. Public availability on YouTube does NOT imply reuse rights.
    3. AI transformation/voiceover does NOT remove copyright obligations.
    4. Creative Commons claims require evidence verification.
    5. Human review is authoritative.
    """
    # 1. User-owned content (Creator's original work)
    if source_class == SourceClass.USER_OWNED:
        reason = "Source verified as user-owned primary material."
        if evidence_reference:
            reason = f"Source verified as user-owned primary material. Evidence: {evidence_reference}."
        return RightsEvaluationResult(
            status=RightsStatus.APPROVED,
            decision_reason=reason,
            requires_human_review=False,
            attribution_required=False,
            conditions=(),
        )

    # 2. Commercial license
    if source_class == SourceClass.COMMERCIAL_LICENSE:
        if not evidence_reference:
            return RightsEvaluationResult(
                status=RightsStatus.REVIEW_REQUIRED,
                decision_reason="Commercial license claimed but lacks evidence reference or contract ID.",
                requires_human_review=True,
                attribution_required=attribution_required,
                conditions=(),
            )
        if not commercial_use or not modification_allowed:
            return RightsEvaluationResult(
                status=RightsStatus.BLOCKED,
                decision_reason="Commercial license terms prohibit commercial use or transformation.",
                requires_human_review=True,
                attribution_required=attribution_required,
                conditions=(),
            )
        conds = ("attribution_required",) if attribution_required else ()
        return RightsEvaluationResult(
            status=RightsStatus.APPROVED,
            decision_reason=f"Valid commercial license verified with evidence: {evidence_reference}.",
            requires_human_review=False,
            attribution_required=attribution_required,
            conditions=conds,
        )

    # 3. Creative Commons
    if source_class == SourceClass.CREATIVE_COMMONS:
        if not evidence_reference:
            return RightsEvaluationResult(
                status=RightsStatus.REVIEW_REQUIRED,
                decision_reason="Creative Commons source requires license verification evidence.",
                requires_human_review=True,
                attribution_required=True,
                conditions=(),
            )
        if license_type == LicenseType.CC_BY_ND:
            return RightsEvaluationResult(
                status=RightsStatus.BLOCKED,
                decision_reason="CC-BY-ND prohibits derivative works and video adaptation.",
                requires_human_review=False,
                attribution_required=True,
                conditions=(),
            )
        if license_type == LicenseType.CC_BY_NC:
            return RightsEvaluationResult(
                status=RightsStatus.BLOCKED,
                decision_reason="CC-BY-NC prohibits commercial use.",
                requires_human_review=True,
                attribution_required=True,
                conditions=(),
            )
        if license_type == LicenseType.CC0:
            conds = ("attribution_required",) if attribution_required else ()
            status = RightsStatus.CONDITIONAL if attribution_required else RightsStatus.APPROVED
            return RightsEvaluationResult(
                status=status,
                decision_reason="CC0 public domain dedication verified. Compatible with reuse.",
                requires_human_review=False,
                attribution_required=attribution_required,
                conditions=conds,
            )
        if license_type == LicenseType.CC_BY_SA:
            conds = (
                ("attribution_required", "share_alike_required") if attribution_required else ("share_alike_required",)
            )
            return RightsEvaluationResult(
                status=RightsStatus.CONDITIONAL,
                decision_reason="CC-BY-SA requires both creator attribution and share-alike licensing for derivatives.",
                requires_human_review=False,
                attribution_required=True,
                conditions=conds,
            )
        if license_type == LicenseType.CC_BY:
            conds = ("attribution_required",) if attribution_required else ()
            status = RightsStatus.CONDITIONAL if attribution_required else RightsStatus.APPROVED
            return RightsEvaluationResult(
                status=status,
                decision_reason="Compatible Creative Commons license (CC-BY) verified. Requires attribution.",
                requires_human_review=False,
                attribution_required=attribution_required,
                conditions=conds,
            )
        return RightsEvaluationResult(
            status=RightsStatus.REVIEW_REQUIRED,
            decision_reason=f"Creative Commons license '{license_type.value}' requires human review to confirm compatibility.",
            requires_human_review=True,
            attribution_required=True,
            conditions=(),
        )

    # 4. Explicit permission-based content
    if source_class == SourceClass.PERMISSION_BASED:
        if not evidence_reference or not reviewer:
            return RightsEvaluationResult(
                status=RightsStatus.REVIEW_REQUIRED,
                decision_reason="Permission-based material requires documented agreement and authorized reviewer.",
                requires_human_review=True,
                attribution_required=attribution_required,
                conditions=(),
            )
        if not commercial_use or not modification_allowed:
            return RightsEvaluationResult(
                status=RightsStatus.BLOCKED,
                decision_reason="Documented permission terms prohibit commercial use or transformation.",
                requires_human_review=True,
                attribution_required=attribution_required,
                conditions=(),
            )
        conds = ("attribution_required",) if attribution_required else ()
        status = RightsStatus.CONDITIONAL if attribution_required else RightsStatus.APPROVED
        return RightsEvaluationResult(
            status=status,
            decision_reason=f"Explicit permission verified by {reviewer}. Reference: {evidence_reference}.",
            requires_human_review=False,
            attribution_required=attribution_required,
            conditions=conds,
        )

    # 5. Unknown rights / Standard YouTube
    return RightsEvaluationResult(
        status=RightsStatus.REVIEW_REQUIRED,
        decision_reason="Unknown or standard copyright source. Public availability does not grant reuse rights.",
        requires_human_review=True,
        attribution_required=True,
        conditions=(),
    )
