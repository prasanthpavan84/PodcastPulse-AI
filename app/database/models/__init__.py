"""Exports all database models for Alembic discovery and application use."""

from app.database.base import Base
from app.database.models.analytics import AnalyticsRecord
from app.database.models.asset import Asset
from app.database.models.audit import AuditEvent
from app.database.models.channel import Channel
from app.database.models.clip import ClipCandidate, ClipScore
from app.database.models.job import Job
from app.database.models.popularity import PopularityScore
from app.database.models.project import Project
from app.database.models.publishing import PublishedVideo, PublishingJob
from app.database.models.quality import QualityCheck
from app.database.models.render import Render
from app.database.models.rights import RightsRecord
from app.database.models.script import Script
from app.database.models.source import Source
from app.database.models.transcript import Transcript, TranscriptSegment
from app.database.models.trend import TrendScore
from app.database.models.user import User

__all__ = [
    "Base",
    "User",
    "Channel",
    "Source",
    "TrendScore",
    "PopularityScore",
    "RightsRecord",
    "Job",
    "Project",
    "Transcript",
    "TranscriptSegment",
    "ClipCandidate",
    "ClipScore",
    "Script",
    "Asset",
    "Render",
    "QualityCheck",
    "PublishingJob",
    "PublishedVideo",
    "AnalyticsRecord",
    "AuditEvent",
]
