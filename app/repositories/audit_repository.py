"""Explicit repository for AuditEvent entities."""

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.audit import AuditEvent


class AuditRepository:
    """Persistence operations for immutable audit records."""

    @staticmethod
    def record_event(
        session: Session,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        previous_state: Optional[str] = None,
        new_state: Optional[str] = None,
        project_id: Optional[str] = None,
        job_id: Optional[str] = None,
        request_id: Optional[str] = None,
        agent_run_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        """Create and flush an audit log entry."""
        # Sanitize payload to never store secrets or tokens
        safe_payload = None
        if payload:
            safe_payload = {
                k: (
                    "***REDACTED***"
                    if any(s in k.lower() for s in ("token", "secret", "password", "key", "auth"))
                    else v
                )
                for k, v in payload.items()
            }

        event = AuditEvent(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            previous_state=previous_state,
            new_state=new_state,
            project_id=project_id,
            job_id=job_id,
            request_id=request_id,
            agent_run_id=agent_run_id,
            payload=safe_payload,
        )
        session.add(event)
        session.flush()
        return event

    @staticmethod
    def list_by_entity(session: Session, entity_type: str, entity_id: str) -> List[AuditEvent]:
        """Retrieve audit history for a specific entity."""
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.entity_type == entity_type, AuditEvent.entity_id == entity_id)
            .order_by(AuditEvent.timestamp.asc())
        )
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def list_by_project(session: Session, project_id: str) -> List[AuditEvent]:
        """Retrieve all audit events for a project."""
        stmt = select(AuditEvent).where(AuditEvent.project_id == project_id).order_by(AuditEvent.timestamp.asc())
        return list(session.execute(stmt).scalars().all())
