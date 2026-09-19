"""Structured domain and application error hierarchy."""

from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Canonical application error codes."""

    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    RIGHTS_BLOCKED = "RIGHTS_BLOCKED"
    RIGHTS_REVIEW_REQUIRED = "RIGHTS_REVIEW_REQUIRED"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppError(Exception):
    """Base application exception with structured output."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        status_code: int = 400,
        details: Optional[Dict[str, Any]] = None,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.retryable = retryable

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error for API responses and audit logs."""
        return {
            "code": self.code.value,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
            "retryable": self.retryable,
        }


class StateTransitionError(AppError):
    """Raised when an illegal workflow state transition is attempted."""

    def __init__(self, current_state: str, requested_state: str, reason: str = ""):
        message = f"Cannot transition from {current_state} to {requested_state}."
        if reason:
            message += f" Reason: {reason}"
        super().__init__(
            code=ErrorCode.INVALID_STATE_TRANSITION,
            message=message,
            status_code=409,
            details={"current_state": current_state, "requested_state": requested_state, "reason": reason},
            retryable=False,
        )


class RightsBlockedError(AppError):
    """Raised when an operation is blocked by rights rules."""

    def __init__(self, source_id: str, reason: str):
        super().__init__(
            code=ErrorCode.RIGHTS_BLOCKED,
            message=f"Source {source_id} is blocked from processing: {reason}",
            status_code=403,
            details={"source_id": source_id, "reason": reason},
            retryable=False,
        )


class NotFoundError(AppError):
    """Raised when a requested resource is not found."""

    def __init__(self, entity_type: str, entity_id: str):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=f"{entity_type} with ID '{entity_id}' not found.",
            status_code=404,
            details={"entity_type": entity_type, "entity_id": entity_id},
            retryable=False,
        )


class DomainValidationError(AppError):
    """Raised when domain business rules are violated."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=422,
            details=details,
            retryable=False,
        )


class DatabaseError(AppError):
    """Raised on relational database exceptions."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None, retryable: bool = False):
        super().__init__(
            code=ErrorCode.DATABASE_ERROR,
            message=message,
            status_code=500,
            details=details,
            retryable=retryable,
        )


class RightsAuthorizationError(AppError):
    """Raised when an unauthorized actor attempts a rights decision or rights mutation."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=403,
            details=details,
            retryable=False,
        )
