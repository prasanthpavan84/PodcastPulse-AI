"""Explicit repository for Project entities."""

from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.project import Project
from app.domain.enums import WorkflowState


class ProjectRepository:
    """Persistence operations for Project lifecycle records."""

    @staticmethod
    def get_by_id(session: Session, project_id: str) -> Optional[Project]:
        """Fetch project by UUID."""
        stmt = select(Project).where(Project.id == project_id, Project.deleted_at.is_(None))
        return session.execute(stmt).scalar_one_or_none()

    @staticmethod
    def get_by_source_id(session: Session, source_id: str) -> List[Project]:
        """Fetch all projects derived from a source."""
        stmt = select(Project).where(Project.source_id == source_id, Project.deleted_at.is_(None))
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def list_projects(
        session: Session,
        state: Optional[WorkflowState] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Project]:
        """List projects optionally filtered by workflow state."""
        stmt = select(Project).where(Project.deleted_at.is_(None))
        if state:
            stmt = stmt.where(Project.state == state)
        stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(limit)
        return list(session.execute(stmt).scalars().all())

    @staticmethod
    def save(session: Session, project: Project) -> Project:
        """Insert or update a project record."""
        session.add(project)
        session.flush()
        return project
