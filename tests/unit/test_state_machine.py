"""Unit tests for the canonical workflow state machine (Pure Domain)."""

import pytest

from app.core.errors import StateTransitionError
from app.domain.enums import WorkflowState
from app.domain.state_machine import can_transition, validate_transition


def test_canonical_happy_path_transitions():
    """Verify that every step of the canonical happy path is permitted."""
    happy_path = [
        WorkflowState.DISCOVERED,
        WorkflowState.RIGHTS_PENDING,
        WorkflowState.RIGHTS_APPROVED,
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
    ]

    for i in range(len(happy_path) - 1):
        curr = happy_path[i]
        nxt = happy_path[i + 1]
        assert can_transition(curr, nxt) is True, f"Failed transition {curr} -> {nxt}"
        validate_transition(curr, nxt)


def test_prohibit_rights_blocked_to_transcribing():
    """Hard Gate Rule: RIGHTS_BLOCKED must NEVER transition to TRANSCRIBING."""
    assert can_transition(WorkflowState.RIGHTS_BLOCKED, WorkflowState.TRANSCRIBING) is False
    with pytest.raises(StateTransitionError) as exc_info:
        validate_transition(WorkflowState.RIGHTS_BLOCKED, WorkflowState.TRANSCRIBING)
    assert "Prohibited by rights safety rules" in str(exc_info.value)


def test_prohibit_rejected_directly_to_published():
    """Human Review Rule: REJECTED content cannot directly become PUBLISHED."""
    for invalid_target in (WorkflowState.PUBLISHED, WorkflowState.READY_TO_PUBLISH, WorkflowState.UPLOADING):
        assert can_transition(WorkflowState.REJECTED, invalid_target) is False
        with pytest.raises(StateTransitionError) as exc_info:
            validate_transition(WorkflowState.REJECTED, invalid_target)
        assert "REJECTED content cannot be published" in str(exc_info.value)


def test_prohibit_bypassing_steps():
    """Ensure arbitrary state bypassing raises StateTransitionError."""
    # Cannot jump from DISCOVERED directly to SCRIPT_READY
    with pytest.raises(StateTransitionError):
        validate_transition(WorkflowState.DISCOVERED, WorkflowState.SCRIPT_READY)

    # Cannot jump from TRANSCRIBING to PUBLISHED
    with pytest.raises(StateTransitionError):
        validate_transition(WorkflowState.TRANSCRIBING, WorkflowState.PUBLISHED)


def test_terminal_archived_state_has_no_outgoing_transitions():
    """ARCHIVED is a terminal state."""
    for state in WorkflowState:
        if state != WorkflowState.ARCHIVED:
            assert can_transition(WorkflowState.ARCHIVED, state) is False
