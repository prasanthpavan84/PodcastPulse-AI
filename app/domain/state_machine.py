"""Canonical workflow state machine and transition validation.

Pure domain module: zero external framework dependencies.
"""

from typing import Any, Dict, Optional, Set

from app.core.errors import StateTransitionError
from app.domain.enums import WorkflowState

# Canonical Transition Matrix: Current State -> Set of Allowed Next States
ALLOWED_TRANSITIONS: Dict[WorkflowState, Set[WorkflowState]] = {
    WorkflowState.DISCOVERED: {
        WorkflowState.RIGHTS_PENDING,
        WorkflowState.FAILED,
        WorkflowState.ARCHIVED,
    },
    WorkflowState.RIGHTS_PENDING: {
        WorkflowState.RIGHTS_APPROVED,
        WorkflowState.RIGHTS_BLOCKED,
        WorkflowState.FAILED,
        WorkflowState.ARCHIVED,
    },
    WorkflowState.RIGHTS_APPROVED: {
        WorkflowState.TRANSCRIBING,
        WorkflowState.FAILED,
        WorkflowState.ARCHIVED,
    },
    WorkflowState.RIGHTS_BLOCKED: {
        # Hard Gate: BLOCKED content cannot proceed to any processing state
        WorkflowState.RIGHTS_PENDING,  # Can only re-enter review upon new human evidence
        WorkflowState.ARCHIVED,
    },
    WorkflowState.TRANSCRIBING: {
        WorkflowState.TRANSCRIBED,
        WorkflowState.FAILED,
    },
    WorkflowState.TRANSCRIBED: {
        WorkflowState.CLIP_ANALYSIS,
        WorkflowState.FAILED,
        WorkflowState.ARCHIVED,
    },
    WorkflowState.CLIP_ANALYSIS: {
        WorkflowState.CLIPS_READY,
        WorkflowState.FAILED,
    },
    WorkflowState.CLIPS_READY: {
        WorkflowState.SCRIPT_READY,
        WorkflowState.FAILED,
        WorkflowState.ARCHIVED,
    },
    WorkflowState.SCRIPT_READY: {
        WorkflowState.VIDEO_RENDERING,
        WorkflowState.REVIEW_PENDING,
        WorkflowState.FAILED,
        WorkflowState.ARCHIVED,
    },
    WorkflowState.VIDEO_RENDERING: {
        WorkflowState.RENDERED,
        WorkflowState.FAILED,
    },
    WorkflowState.RENDERED: {
        WorkflowState.QC_PENDING,
        WorkflowState.FAILED,
    },
    WorkflowState.QC_PENDING: {
        WorkflowState.QC_PASSED,
        WorkflowState.REJECTED,
        WorkflowState.VIDEO_RENDERING,  # Retry rendering if transient QC defect
        WorkflowState.FAILED,
    },
    WorkflowState.QC_PASSED: {
        WorkflowState.REVIEW_PENDING,
        WorkflowState.FAILED,
    },
    WorkflowState.REVIEW_PENDING: {
        WorkflowState.APPROVED,
        WorkflowState.REJECTED,
        WorkflowState.SCRIPT_READY,  # Return for script rework
    },
    WorkflowState.APPROVED: {
        WorkflowState.READY_TO_PUBLISH,
        WorkflowState.REJECTED,  # Human can revoke approval before publish
        WorkflowState.ARCHIVED,
    },
    WorkflowState.REJECTED: {
        WorkflowState.REVIEW_PENDING,  # Re-evaluate
        WorkflowState.SCRIPT_READY,  # Send back to rework
        WorkflowState.ARCHIVED,
    },
    WorkflowState.READY_TO_PUBLISH: {
        WorkflowState.UPLOADING,
        WorkflowState.APPROVED,  # Hold back
        WorkflowState.ARCHIVED,
    },
    WorkflowState.UPLOADING: {
        WorkflowState.PUBLISHED,
        WorkflowState.READY_TO_PUBLISH,  # Retry upload
        WorkflowState.FAILED,
    },
    WorkflowState.PUBLISHED: {
        WorkflowState.ARCHIVED,
    },
    WorkflowState.FAILED: {
        WorkflowState.ARCHIVED,
    },
    WorkflowState.ARCHIVED: set(),  # Terminal state
}


def can_transition(current_state: WorkflowState, requested_state: WorkflowState) -> bool:
    """Check whether a transition between two states is valid."""
    allowed = ALLOWED_TRANSITIONS.get(current_state, set())
    return requested_state in allowed


def validate_transition(
    current_state: WorkflowState,
    requested_state: WorkflowState,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Validate state transition rules; raise StateTransitionError if prohibited.

    Enforces:
    - No state bypassing.
    - RIGHTS_BLOCKED can never transition to TRANSCRIBING.
    - REJECTED can never transition directly to PUBLISHED.
    - Explicit human approval required for publishing.
    """
    if current_state == requested_state:
        return

    # Hard gate checks
    if current_state == WorkflowState.RIGHTS_BLOCKED and requested_state == WorkflowState.TRANSCRIBING:
        raise StateTransitionError(
            current_state.value,
            requested_state.value,
            "Prohibited by rights safety rules: BLOCKED content cannot enter transcription.",
        )

    if current_state == WorkflowState.REJECTED and requested_state in {
        WorkflowState.PUBLISHED,
        WorkflowState.READY_TO_PUBLISH,
        WorkflowState.UPLOADING,
    }:
        raise StateTransitionError(
            current_state.value,
            requested_state.value,
            "Prohibited: REJECTED content cannot be published without human approval.",
        )

    if not can_transition(current_state, requested_state):
        raise StateTransitionError(
            current_state.value,
            requested_state.value,
            f"Allowed transitions from {current_state.value}: "
            f"{[s.value for s in ALLOWED_TRANSITIONS.get(current_state, set())]}",
        )
