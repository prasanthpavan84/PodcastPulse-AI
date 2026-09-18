"""Audit event model capturing all state transitions and critical mutations."""

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin, utc_now


class AuditEvent(Base, UUIDPrimaryKeyMixin):
    """Immutable audit ledger of all domain transitions, approvals, and mutations."""

    __tablename__ = "audit_events"

    actor: Mapped[str] = mapped_column(String(100), default="system", nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    previous_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    project_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    agent_run_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
