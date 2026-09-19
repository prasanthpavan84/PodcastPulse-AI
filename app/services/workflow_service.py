"""Transactional workflow state transition service."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, StateTransitionError
from app.core.logging import get_logger
from app.domain.enums import WorkflowState
from app.domain.state_machine import validate_transition
from app.repositories.audit_repository import AuditRepository
from app.repositories.project_repository import ProjectRepository
from app.repositories.source_repository import SourceRepository

logger = get_logger("workflow_service")


class WorkflowService:
    """Orchestrates transactional workflow state transitions with mandatory audit logging."""

    @staticmethod
    def transition_source(
        session: Session,
        source_id: str,
        requested_state: WorkflowState,
        actor: str = "system",
        reason: str = "",
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """Transition a Source entity to a new workflow state transactionally."""
        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)

        current_state = source.workflow_state

        # 1. Hard Rights Gate: Unapproved or invalid rights sources can never enter TRANSCRIBING
        if requested_state == WorkflowState.TRANSCRIBING:
            from app.services.rights_service import RightsService

            try:
                RightsService.validate_rights_gate(session, source_id=source_id)
            except Exception as exc:
                raise StateTransitionError(
                    current_state.value,
                    requested_state.value,
                    f"Rights gate check failed: {str(exc)}",
                ) from exc

        # 2. Validate transition through domain state machine
        validate_transition(current_state, requested_state, context={"source_id": source_id, "reason": reason})

        # 2. Mutate entity
        source.workflow_state = requested_state
        SourceRepository.save(session, source)

        # 3. Create audit event
        audit_payload = payload or {}
        if reason:
            audit_payload["reason"] = reason

        AuditRepository.record_event(
            session=session,
            actor=actor,
            action=f"TRANSITION_{current_state.value}_TO_{requested_state.value}",
            entity_type="Source",
            entity_id=source_id,
            previous_state=current_state.value,
            new_state=requested_state.value,
            project_id=None,
            job_id=job_id,
            request_id=request_id,
            agent_run_id=agent_run_id,
            payload=audit_payload,
        )

        logger.info(
            "source_state_transitioned",
            source_id=source_id,
            previous_state=current_state.value,
            new_state=requested_state.value,
            actor=actor,
        )
        return requested_state

    @staticmethod
    def transition_project(
        session: Session,
        project_id: str,
        requested_state: WorkflowState,
        actor: str = "system",
        reason: str = "",
        request_id: Optional[str] = None,
        job_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """Transition a Project entity to a new workflow state transactionally."""
        project = ProjectRepository.get_by_id(session, project_id)
        if not project:
            raise NotFoundError("Project", project_id)

        current_state = project.state

        # Enforce rights gate for downstream project processing states
        downstream_processing_states = {
            WorkflowState.TRANSCRIBING,
            WorkflowState.TRANSCRIBED,
            WorkflowState.CLIP_ANALYSIS,
            WorkflowState.CLIPS_READY,
            WorkflowState.SCRIPT_READY,
            WorkflowState.VIDEO_RENDERING,
            WorkflowState.RENDERED,
            WorkflowState.QC_PENDING,
            WorkflowState.QC_PASSED,
            WorkflowState.REVIEW_PENDING,
            WorkflowState.APPROVED,
            WorkflowState.READY_TO_PUBLISH,
            WorkflowState.UPLOADING,
            WorkflowState.PUBLISHED,
        }
        if requested_state in downstream_processing_states:
            from app.services.rights_service import RightsService

            try:
                RightsService.validate_rights_gate(
                    session,
                    source_id=project.source_id,
                    target_project_id=project.id,
                )
            except Exception as exc:
                raise StateTransitionError(
                    current_state.value,
                    requested_state.value,
                    f"Rights gate check failed for project '{project_id}': {str(exc)}",
                ) from exc

        # 1. Validate transition through domain state machine
        validate_transition(current_state, requested_state, context={"project_id": project_id, "reason": reason})

        # 2. Mutate entity
        project.state = requested_state
        ProjectRepository.save(session, project)

        # 3. Create audit event
        audit_payload = payload or {}
        if reason:
            audit_payload["reason"] = reason

        AuditRepository.record_event(
            session=session,
            actor=actor,
            action=f"TRANSITION_{current_state.value}_TO_{requested_state.value}",
            entity_type="Project",
            entity_id=project_id,
            previous_state=current_state.value,
            new_state=requested_state.value,
            project_id=project_id,
            job_id=job_id,
            request_id=request_id,
            agent_run_id=agent_run_id,
            payload=audit_payload,
        )

        logger.info(
            "project_state_transitioned",
            project_id=project_id,
            previous_state=current_state.value,
            new_state=requested_state.value,
            actor=actor,
        )
        return requested_state
