"""Rights service executing deterministic evaluation, human review, and clearance."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import DomainValidationError, NotFoundError, RightsAuthorizationError, RightsBlockedError
from app.core.logging import get_logger
from app.database.models.rights import RightsRecord
from app.domain.enums import EvidenceStatus, LicenseType, ReviewerRole, RightsStatus, SourceClass, WorkflowState
from app.domain.rights_rules import evaluate_rights, validate_evidence
from app.repositories.audit_repository import AuditRepository
from app.repositories.rights_repository import RightsRepository
from app.repositories.source_repository import SourceRepository
from app.services.workflow_service import WorkflowService

logger = get_logger("rights_service")


class RightsService:
    """Evaluates rights, validates evidence, enforces human authorization, and transitions states."""

    @staticmethod
    def get_by_source_id(session: Session, source_id: str) -> Optional[RightsRecord]:
        """Fetch rights clearance record for a source."""
        return RightsRepository.get_by_source_id(session, source_id)

    @staticmethod
    def evaluate_and_record(
        session: Session,
        source_id: str,
        source_class: SourceClass,
        license_type: LicenseType,
        commercial_use: bool = False,
        modification_allowed: bool = False,
        attribution_required: bool = True,
        evidence_reference: Optional[str] = None,
        evidence_type: Optional[str] = None,
        reviewer: Optional[str] = None,
        request_id: Optional[str] = None,
        project_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> RightsRecord:
        """Run deterministic rules-based evaluation and record preliminary rights status."""
        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)

        # 1. Run domain evaluation
        result = evaluate_rights(
            source_class=source_class,
            license_type=license_type,
            commercial_use=commercial_use,
            modification_allowed=modification_allowed,
            attribution_required=attribution_required,
            evidence_reference=evidence_reference,
            reviewer=reviewer,
        )

        # Map initial evidence status from evaluation result
        if source_class == SourceClass.USER_OWNED:
            evidence_status = EvidenceStatus.OWNED
        elif source_class == SourceClass.COMMERCIAL_LICENSE and result.status == RightsStatus.APPROVED:
            evidence_status = EvidenceStatus.LICENSED
        elif source_class == SourceClass.CREATIVE_COMMONS and result.status in {
            RightsStatus.APPROVED,
            RightsStatus.CONDITIONAL,
        }:
            evidence_status = EvidenceStatus.CREATIVE_COMMONS_VERIFIED
        elif source_class == SourceClass.PERMISSION_BASED and result.status in {
            RightsStatus.APPROVED,
            RightsStatus.CONDITIONAL,
        }:
            evidence_status = EvidenceStatus.PERMISSION_GRANTED
        elif result.status == RightsStatus.BLOCKED:
            evidence_status = EvidenceStatus.REJECTED
        else:
            evidence_status = EvidenceStatus.UNKNOWN

        # 2. Persist/update RightsRecord
        record = RightsRepository.get_by_source_id(session, source_id)
        if not record:
            record = RightsRecord(source_id=source_id)

        record.source_class = source_class
        record.license_type = license_type
        record.evidence_status = evidence_status
        record.project_id = project_id
        record.commercial_use = commercial_use
        record.modification_allowed = modification_allowed
        record.attribution_required = result.attribution_required
        record.evidence_reference = evidence_reference
        record.evidence_type = evidence_type
        record.reviewer = reviewer
        record.decision = result.status
        record.decision_reason = result.decision_reason
        record.ruleset_version = result.ruleset_version
        record.verified_at = datetime.now(timezone.utc)
        record.expires_at = expires_at

        RightsRepository.save(session, record)

        # 3. Update source metadata
        source.source_class = source_class
        source.license_type = license_type
        source.rights_status = result.status
        SourceRepository.save(session, source)

        # 4. Advance workflow state respecting canonical transition paths
        if result.status == RightsStatus.APPROVED:
            target_state = WorkflowState.RIGHTS_APPROVED
        elif result.status == RightsStatus.BLOCKED:
            target_state = WorkflowState.RIGHTS_BLOCKED
        else:
            target_state = WorkflowState.RIGHTS_PENDING

        if source.workflow_state == WorkflowState.DISCOVERED:
            WorkflowService.transition_source(
                session=session,
                source_id=source_id,
                requested_state=WorkflowState.RIGHTS_PENDING,
                actor=reviewer or "rights_engine",
                reason="Submitting source for rights evaluation.",
                request_id=request_id,
                payload={"action": "rights_intake"},
            )

        if source.workflow_state == WorkflowState.RIGHTS_BLOCKED and target_state != WorkflowState.RIGHTS_BLOCKED:
            WorkflowService.transition_source(
                session=session,
                source_id=source_id,
                requested_state=WorkflowState.RIGHTS_PENDING,
                actor=reviewer or "rights_engine",
                reason="Re-evaluating previously blocked source with new evidence.",
                request_id=request_id,
                payload={"action": "rights_reevaluation"},
            )

        if source.workflow_state != target_state:
            WorkflowService.transition_source(
                session=session,
                source_id=source_id,
                requested_state=target_state,
                actor=reviewer or "rights_engine",
                reason=result.decision_reason,
                request_id=request_id,
                payload={"rights_decision": result.status.value},
            )

        # 5. Record dedicated audit event
        AuditRepository.record_event(
            session=session,
            actor=reviewer or "rights_engine",
            action=f"RIGHTS_EVALUATION_{result.status.value}",
            entity_type="Source",
            entity_id=source_id,
            previous_state=None,
            new_state=result.status.value,
            project_id=project_id,
            request_id=request_id,
            payload={
                "source_class": source_class.value,
                "license_type": license_type.value,
                "evidence_status": evidence_status.value,
                "decision": result.status.value,
                "reason": result.decision_reason,
                "conditions": list(result.conditions),
                "attribution_required": result.attribution_required,
                "evidence_reference": evidence_reference,
                "evidence_type": evidence_type,
                "ruleset_version": result.ruleset_version,
            },
        )

        logger.info(
            "rights_evaluated",
            source_id=source_id,
            decision=result.status.value,
            reason=result.decision_reason,
        )
        return record

    @staticmethod
    def record_human_decision(
        session: Session,
        source_id: str,
        decision: RightsStatus,
        evidence_status: EvidenceStatus,
        reviewer: str,
        reviewer_role: str,
        decision_reason: str,
        evidence_reference: Optional[str] = None,
        evidence_type: Optional[str] = None,
        evidence_timestamp: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        project_id: Optional[str] = None,
        commercial_use: Optional[bool] = None,
        modification_allowed: Optional[bool] = None,
        attribution_required: Optional[bool] = None,
        request_id: Optional[str] = None,
    ) -> RightsRecord:
        """Atomically validate evidence, verify authorized human review, update state, and audit."""
        # 1. Enforce human authorization boundary
        if not reviewer or not reviewer.strip():
            raise RightsAuthorizationError("Reviewer identifier is required for human rights review.")

        if not ReviewerRole.is_authorized_human(reviewer_role):
            raise RightsAuthorizationError(
                f"Unauthorized reviewer: role '{reviewer_role}' is not an authorized human reviewer. "
                "AI/automated systems are prohibited from creating final rights decisions."
            )

        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)

        # 2. Deterministic evidence validation
        validation_res = validate_evidence(
            source_id=source.id,
            target_source_id=source_id,
            evidence_status=evidence_status,
            decision=decision,
            evidence_reference=evidence_reference,
            evidence_timestamp=evidence_timestamp,
            expires_at=expires_at,
            reviewer=reviewer,
            reviewer_role=reviewer_role,
            source_class=source.source_class,
            license_type=source.license_type,
            project_id=project_id,
            target_project_id=project_id,
        )

        if not validation_res.is_valid:
            raise DomainValidationError(
                validation_res.reason,
                details={"errors": list(validation_res.errors)},
            )

        # 3. Update RightsRecord
        record = RightsRepository.get_by_source_id(session, source_id)
        if not record:
            record = RightsRecord(source_id=source_id)

        record.evidence_status = validation_res.evidence_status
        record.project_id = project_id
        record.reviewer = reviewer
        record.decision = decision
        record.decision_reason = decision_reason
        record.evidence_reference = evidence_reference
        record.evidence_type = evidence_type
        record.evidence_timestamp = evidence_timestamp
        record.expires_at = expires_at
        record.verified_at = datetime.now(timezone.utc)
        if commercial_use is not None:
            record.commercial_use = commercial_use
        if modification_allowed is not None:
            record.modification_allowed = modification_allowed
        if attribution_required is not None:
            record.attribution_required = attribution_required

        RightsRepository.save(session, record)

        # 4. Update Source metadata
        source.rights_status = decision
        SourceRepository.save(session, source)

        # 5. Workflow state progression
        if decision == RightsStatus.APPROVED:
            target_state = WorkflowState.RIGHTS_APPROVED
            audit_action = "RIGHTS_APPROVAL_GRANTED"
        elif decision == RightsStatus.BLOCKED:
            target_state = WorkflowState.RIGHTS_BLOCKED
            audit_action = "RIGHTS_APPROVAL_REJECTED"
        else:
            target_state = WorkflowState.RIGHTS_PENDING
            audit_action = "RIGHTS_REVIEW_REQUESTED"

        if source.workflow_state == WorkflowState.DISCOVERED:
            WorkflowService.transition_source(
                session=session,
                source_id=source_id,
                requested_state=WorkflowState.RIGHTS_PENDING,
                actor=reviewer,
                reason="Submitting source for human rights review.",
                request_id=request_id,
                payload={"action": "human_review_intake"},
            )

        if source.workflow_state == WorkflowState.RIGHTS_BLOCKED and target_state != WorkflowState.RIGHTS_BLOCKED:
            WorkflowService.transition_source(
                session=session,
                source_id=source_id,
                requested_state=WorkflowState.RIGHTS_PENDING,
                actor=reviewer,
                reason="Re-evaluating blocked source via human review.",
                request_id=request_id,
                payload={"action": "human_review_reevaluation"},
            )

        if source.workflow_state != target_state:
            WorkflowService.transition_source(
                session=session,
                source_id=source_id,
                requested_state=target_state,
                actor=reviewer,
                reason=decision_reason,
                request_id=request_id,
                payload={"human_decision": decision.value},
            )

        # 6. Audit event
        AuditRepository.record_event(
            session=session,
            actor=reviewer,
            action=audit_action,
            entity_type="Source",
            entity_id=source_id,
            project_id=project_id,
            request_id=request_id,
            payload={
                "reviewer": reviewer,
                "reviewer_role": reviewer_role,
                "decision": decision.value,
                "evidence_status": validation_res.evidence_status.value,
                "decision_reason": decision_reason,
                "evidence_reference": evidence_reference,
                "expires_at": expires_at.isoformat() if expires_at else None,
            },
        )

        logger.info(
            "human_rights_decision_recorded",
            source_id=source_id,
            reviewer=reviewer,
            decision=decision.value,
            evidence_status=validation_res.evidence_status.value,
        )
        return record

    @staticmethod
    def validate_rights_gate(
        session: Session,
        source_id: str,
        target_source_id: Optional[str] = None,
        project_id: Optional[str] = None,
        target_project_id: Optional[str] = None,
        reference_time: Optional[datetime] = None,
    ) -> None:
        """Enforce canonical rights gate invariant.

        Invariant:
        rights_status == APPROVED
        AND workflow_state == RIGHTS_APPROVED
        AND evidence is valid
        AND evidence is not expired
        AND required human authorization exists
        AND source binding matches
        AND project binding matches
        """
        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)

        effective_target_source = target_source_id or source_id
        if source.id != effective_target_source:
            raise RightsBlockedError(
                source_id,
                f"Source mismatch: approval is bound to '{source.id}', cannot authorize target '{effective_target_source}'.",
            )

        if source.rights_status != RightsStatus.APPROVED:
            raise RightsBlockedError(
                source_id,
                f"Rights gate check failed: source '{source_id}' has rights_status={source.rights_status.value}. "
                "Unrestricted downstream processing requires APPROVED rights status.",
            )

        record = RightsRepository.get_by_source_id(session, source_id)
        if not record:
            raise RightsBlockedError(
                source_id,
                f"Rights gate check failed: no RightsRecord found for source '{source_id}'.",
            )

        if record.decision != RightsStatus.APPROVED:
            raise RightsBlockedError(
                source_id,
                f"Rights gate check failed: RightsRecord decision is {record.decision.value}.",
            )

        # Validate evidence freshness, bindings, and reviewer presence
        val_res = validate_evidence(
            source_id=record.source_id,
            target_source_id=effective_target_source,
            evidence_status=record.evidence_status,
            decision=record.decision,
            evidence_reference=record.evidence_reference,
            evidence_timestamp=record.evidence_timestamp,
            expires_at=record.expires_at,
            reviewer=record.reviewer,
            reviewer_role=ReviewerRole.EDITOR.value if record.reviewer else None,
            source_class=record.source_class,
            license_type=record.license_type,
            reference_time=reference_time,
            project_id=record.project_id,
            target_project_id=target_project_id or project_id,
        )

        if not val_res.is_valid:
            raise RightsBlockedError(source_id, f"Rights gate check failed: {val_res.reason}")
