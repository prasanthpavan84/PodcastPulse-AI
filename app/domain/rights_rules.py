"""Deterministic, evidence-based content rights evaluation rules.

Pure domain module: zero external framework dependencies.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.domain.enums import EvidenceStatus, LicenseType, ReviewerRole, RightsStatus, SourceClass


@dataclass(frozen=True)
class EvidenceValidationResult:
    """Result of deterministic evidence verification."""

    is_valid: bool
    evidence_status: EvidenceStatus
    errors: tuple[str, ...] = ()
    reason: str = ""


@dataclass(frozen=True)
class RightsEvaluationResult:
    """Outcome of deterministic rights evaluation."""

    status: RightsStatus
    decision_reason: str
    requires_human_review: bool
    attribution_required: bool
    conditions: tuple[str, ...] = ()
    ruleset_version: str = "1.0.0"


def validate_evidence(
    source_id: str,
    target_source_id: str,
    evidence_status: EvidenceStatus,
    decision: RightsStatus,
    evidence_reference: Optional[str] = None,
    evidence_timestamp: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    reviewer: Optional[str] = None,
    reviewer_role: Optional[str] = None,
    source_class: Optional[SourceClass] = None,
    license_type: Optional[LicenseType] = None,
    reference_time: Optional[datetime] = None,
    project_id: Optional[str] = None,
    target_project_id: Optional[str] = None,
) -> EvidenceValidationResult:
    """Deterministically validate evidence, reviewer authorization, bindings, and expiry.

    Enforces:
    1. Source binding: evidence tied to source_id must match target_source_id.
    2. Project binding: evidence tied to project_id must match target_project_id when specified.
    3. Expiry: expired evidence cannot approve or process.
    4. Human authorization: reviewer identity and authorized human role required for approval; AI/LLM forbidden.
    5. Creative Commons safety: label alone is insufficient; documented verification required.
    6. Decision consistency: UNKNOWN, REJECTED, or EXPIRED evidence cannot produce APPROVED.
    """
    errors: list[str] = []
    now = reference_time or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Source binding
    if source_id != target_source_id:
        errors.append(
            f"Source mismatch: evidence is bound to source '{source_id}', cannot authorize target '{target_source_id}'."
        )

    # 2. Project binding
    if project_id is not None and target_project_id is not None and project_id != target_project_id:
        errors.append(
            f"Project mismatch: evidence is bound to project '{project_id}', cannot authorize target '{target_project_id}'."
        )

    # 3. Expiration checks
    effective_status = evidence_status
    if expires_at is not None:
        exp = expires_at if expires_at.tzinfo is not None else expires_at.replace(tzinfo=timezone.utc)
        if exp <= now:
            effective_status = EvidenceStatus.EXPIRED
            errors.append(f"Evidence expired at {exp.isoformat()}. Current reference time is {now.isoformat()}.")
    elif evidence_status == EvidenceStatus.EXPIRED:
        errors.append("Evidence status is EXPIRED.")

    # 4. Consistency with decision
    if decision == RightsStatus.APPROVED:
        if effective_status in {EvidenceStatus.UNKNOWN, EvidenceStatus.REJECTED, EvidenceStatus.EXPIRED}:
            errors.append(f"Cannot grant APPROVED rights when evidence status is {effective_status.value}.")

        # Human authorization requirement
        if not reviewer or not reviewer.strip():
            errors.append("Human authorization required: reviewer identifier is missing.")
        elif not ReviewerRole.is_authorized_human(reviewer_role):
            errors.append(
                f"Unauthorized reviewer: role '{reviewer_role}' is not an authorized human reviewer role. "
                "AI/automated systems are prohibited from creating final rights approvals."
            )

        # Creative Commons safety
        if source_class == SourceClass.CREATIVE_COMMONS:
            if effective_status != EvidenceStatus.CREATIVE_COMMONS_VERIFIED:
                errors.append(
                    "Creative Commons claims require documented verification producing CREATIVE_COMMONS_VERIFIED. "
                    "Unverified platform labels cannot authorize rights approval."
                )
            if not evidence_reference or not evidence_reference.strip():
                errors.append("Creative Commons verification requires documented evidence reference URL or document.")

        # Permission-based safety
        if source_class == SourceClass.PERMISSION_BASED:
            if effective_status != EvidenceStatus.PERMISSION_GRANTED:
                errors.append("Permission-based content requires documented consent producing PERMISSION_GRANTED.")
            if not evidence_reference or not evidence_reference.strip():
                errors.append("Permission-based content requires documented consent agreement reference.")

        # Commercial license safety
        if source_class == SourceClass.COMMERCIAL_LICENSE:
            if effective_status != EvidenceStatus.LICENSED:
                errors.append("Commercial license requires verified license evidence status LICENSED.")
            if not evidence_reference or not evidence_reference.strip():
                errors.append("Commercial license requires documented license contract or invoice reference.")

    is_valid = len(errors) == 0
    reason = "Evidence validation passed." if is_valid else "; ".join(errors)

    return EvidenceValidationResult(
        is_valid=is_valid,
        evidence_status=effective_status,
        errors=tuple(errors),
        reason=reason,
    )


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
