"""Application service orchestrating application use cases."""

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.database.models.project import Project
from app.database.models.source import Source
from app.domain.enums import WorkflowState
from app.repositories.project_repository import ProjectRepository
from app.repositories.source_repository import SourceRepository
from app.services.workflow_service import WorkflowService

logger = get_logger("application_service")


class ContentApplicationService:
    """Application use case coordinator connecting API routes to domain services and repositories."""

    @staticmethod
    def create_project_from_source(
        session: Session,
        source_id: str,
        title: str,
        actor: str = "creator",
        request_id: Optional[str] = None,
    ) -> Project:
        """Create a new project from an approved or pending source."""
        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)

        project = Project(
            source_id=source_id,
            title=title,
            state=source.workflow_state,
        )
        ProjectRepository.save(session, project)

        logger.info("project_created", project_id=project.id, source_id=source_id, title=title)
        return project

    @staticmethod
    def get_source_details(session: Session, source_id: str) -> Source:
        """Retrieve source details by ID."""
        source = SourceRepository.get_by_id(session, source_id)
        if not source:
            raise NotFoundError("Source", source_id)
        return source

    @staticmethod
    def list_sources(
        session: Session,
        state: Optional[WorkflowState] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Source]:
        """List sources with optional state filter."""
        return SourceRepository.list_sources(session, workflow_state=state, limit=limit, offset=offset)

    @staticmethod
    def transition_project_state(
        session: Session,
        project_id: str,
        new_state: WorkflowState,
        actor: str,
        reason: str = "",
        request_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> WorkflowState:
        """Orchestrate project state mutation transactionally."""
        return WorkflowService.transition_project(
            session=session,
            project_id=project_id,
            requested_state=new_state,
            actor=actor,
            reason=reason,
            request_id=request_id,
            payload=payload,
        )
