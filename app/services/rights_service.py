"""Rights service executing deterministic evaluation and clearance."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.database.models.rights import RightsRecord
from app.domain.enums import LicenseType, RightsStatus, SourceClass, WorkflowState
from app.domain.rights_rules import evaluate_rights
from app.repositories.audit_repository import AuditRepository
from app.repositories.rights_repository import RightsRepository
from app.repositories.source_repository import SourceRepository
from app.services.workflow_service import WorkflowService

logger = get_logger("rights_service")


class RightsService:
    """Evaluates rights, persists evidence, and transitions source workflow states."""

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
    ) -> RightsRecord:
        """Run deterministic rights evaluation, update rights record, and advance workflow."""
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

        # 2. Persist/update RightsRecord
        record = RightsRepository.get_by_source_id(session, source_id)
        if not record:
            record = RightsRecord(source_id=source_id)

        record.source_class = source_class
        record.license_type = license_type
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

        # Canonical path: DISCOVERED -> RIGHTS_PENDING -> (RIGHTS_APPROVED | RIGHTS_BLOCKED)
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

        # Re-evaluation path: RIGHTS_BLOCKED -> RIGHTS_PENDING -> target_state
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

        # 5. Record dedicated audit event for rights evaluation
        AuditRepository.record_event(
            session=session,
            actor=reviewer or "rights_engine",
            action=f"RIGHTS_EVALUATION_{result.status.value}",
            entity_type="Source",
            entity_id=source_id,
            previous_state=None,
            new_state=result.status.value,
            request_id=request_id,
            payload={
                "source_class": source_class.value,
                "license_type": license_type.value,
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
