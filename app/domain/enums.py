"""Domain enums and canonical status definitions.

Isolated pure domain layer — no framework or database dependencies.
"""

from enum import Enum


class WorkflowState(str, Enum):
    """Canonical workflow states for PodcastPulse AI content lifecycle."""

    # Discovery & Rights Gates
    DISCOVERED = "DISCOVERED"
    RIGHTS_PENDING = "RIGHTS_PENDING"
    RIGHTS_APPROVED = "RIGHTS_APPROVED"
    RIGHTS_BLOCKED = "RIGHTS_BLOCKED"

    # Transcription
    TRANSCRIBING = "TRANSCRIBING"
    TRANSCRIBED = "TRANSCRIBED"

    # Clip Intelligence
    CLIP_ANALYSIS = "CLIP_ANALYSIS"
    CLIPS_READY = "CLIPS_READY"

    # Script Generation
    SCRIPT_READY = "SCRIPT_READY"

    # Media Rendering
    VIDEO_RENDERING = "VIDEO_RENDERING"
    RENDERED = "RENDERED"

    # Quality Control
    QC_PENDING = "QC_PENDING"
    QC_PASSED = "QC_PASSED"

    # Editorial Review & Approval Gate
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"

    # Publishing
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    UPLOADING = "UPLOADING"
    PUBLISHED = "PUBLISHED"

    # Terminal / Failure States
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class JobStatus(str, Enum):
    """Job execution states."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    RETRYING = "RETRYING"


class JobType(str, Enum):
    """Canonical job execution types."""

    DISCOVERY_JOB = "DISCOVERY_JOB"
    TRANSCRIPTION_JOB = "TRANSCRIPTION_JOB"
    CLIP_ANALYSIS_JOB = "CLIP_ANALYSIS_JOB"
    SCRIPT_GENERATION_JOB = "SCRIPT_GENERATION_JOB"
    VOICE_GENERATION_JOB = "VOICE_GENERATION_JOB"
    VIDEO_RENDER_JOB = "VIDEO_RENDER_JOB"
    QC_JOB = "QC_JOB"
    UPLOAD_JOB = "UPLOAD_JOB"
    ANALYTICS_JOB = "ANALYTICS_JOB"


class SourceClass(str, Enum):
    """Readable rights classes with legacy class mapping."""

    USER_OWNED = "USER_OWNED"
    COMMERCIAL_LICENSE = "COMMERCIAL_LICENSE"
    CREATIVE_COMMONS = "CREATIVE_COMMONS"
    PERMISSION_BASED = "PERMISSION_BASED"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_legacy_code(cls, code: str) -> "SourceClass":
        """Convert legacy CLASS_A-E codes to readable names."""
        mapping = {
            "CLASS_A": cls.USER_OWNED,
            "CLASS_B": cls.COMMERCIAL_LICENSE,
            "CLASS_C": cls.CREATIVE_COMMONS,
            "CLASS_D": cls.PERMISSION_BASED,
            "CLASS_E": cls.UNKNOWN,
        }
        return mapping.get(code.upper(), cls.UNKNOWN)


class RightsStatus(str, Enum):
    """Rights clearance status."""

    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class LicenseType(str, Enum):
    """Standardized license identifiers."""

    OWNED = "OWNED"
    COMMERCIAL = "COMMERCIAL"
    CC_BY = "CC_BY"
    CC_BY_SA = "CC_BY_SA"
    CC_BY_NC = "CC_BY_NC"
    CC_BY_ND = "CC_BY_ND"
    CC0 = "CC0"
    STANDARD_YOUTUBE = "STANDARD_YOUTUBE"
    UNKNOWN = "UNKNOWN"
