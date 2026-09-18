"""Project model representing the content production lifecycle."""

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin
from app.domain.enums import WorkflowState


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    """Content project orchestrating the transformation of a source into a Short."""

    __tablename__ = "projects"

    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[WorkflowState] = mapped_column(
        Enum(WorkflowState),
        default=WorkflowState.DISCOVERED,
        nullable=False,
        index=True,
    )
    algorithm_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)

    # Relationships
    jobs = relationship("Job", back_populates="project", cascade="all, delete-orphan")
    scripts = relationship("Script", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    renders = relationship("Render", back_populates="project", cascade="all, delete-orphan")
