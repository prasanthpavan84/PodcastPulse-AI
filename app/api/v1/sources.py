"""Source rights clearance endpoints."""

from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.logging import ctx_request_id, get_logger
from app.database.session import get_db
from app.domain.enums import LicenseType, RightsStatus, SourceClass, WorkflowState
from app.repositories.source_repository import SourceRepository
from app.services.rights_service import RightsService

logger = get_logger("sources_api")

router = APIRouter()


class RightsEvaluationRequest(BaseModel):
    """Payload for submitting rights clearance evidence."""

    source_class: SourceClass = Field(..., description="Classification of source ownership or license model")
    license_type: LicenseType = Field(..., description="Specific license applied to the source")
    commercial_use: bool = Field(default=False, description="Whether license explicitly permits commercial use")
    modification_allowed: bool = Field(
        default=False, description="Whether license explicitly permits derivative works/adaptation"
    )
    attribution_required: bool = Field(default=True, description="Whether creator attribution is required")
    evidence_reference: Optional[str] = Field(
        default=None, max_length=1024, description="Contract ID, URL, invoice, or agreement reference"
    )
    evidence_type: Optional[str] = Field(
        default=None, max_length=100, description="Type of evidence e.g. URL, contract, email_consent"
    )
    reviewer: Optional[str] = Field(
        default=None, max_length=255, description="Authorized human reviewer username or ID"
    )


class RightsEvaluationResponse(BaseModel):
    """Structured response representing evaluated rights record and workflow state."""

    source_id: str
    rights_status: RightsStatus
    workflow_state: WorkflowState
    source_class: SourceClass
    license_type: LicenseType
    decision_reason: Optional[str] = None
    attribution_required: bool
    conditions: List[str] = Field(default_factory=list)
    verified_at: Optional[datetime] = None
    evidence_reference: Optional[str] = None
    reviewer: Optional[str] = None
    ruleset_version: str = "1.0.0"


@router.post(
    "/{source_id}/rights",
    response_model=RightsEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit and evaluate content rights evidence for a source",
)
def evaluate_source_rights(
    source_id: str,
    request_data: RightsEvaluationRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> RightsEvaluationResponse:
    """Evaluate source reuse permissions deterministically, persist rights record, advance workflow, and audit."""
    req_id = ctx_request_id.get() or request.headers.get("X-Request-ID")

    record = RightsService.evaluate_and_record(
        session=session,
        source_id=source_id,
        source_class=request_data.source_class,
        license_type=request_data.license_type,
        commercial_use=request_data.commercial_use,
        modification_allowed=request_data.modification_allowed,
        attribution_required=request_data.attribution_required,
        evidence_reference=request_data.evidence_reference,
        evidence_type=request_data.evidence_type,
        reviewer=request_data.reviewer,
        request_id=req_id,
    )

    session.commit()

    source = SourceRepository.get_by_id(session, source_id)
    workflow_state = source.workflow_state if source else WorkflowState.RIGHTS_PENDING

    conditions: List[str] = []
    if record.decision == RightsStatus.CONDITIONAL:
        if record.attribution_required:
            conditions.append("attribution_required")
        if record.license_type == LicenseType.CC_BY_SA:
            conditions.append("share_alike_required")

    return RightsEvaluationResponse(
        source_id=record.source_id,
        rights_status=record.decision,
        workflow_state=workflow_state,
        source_class=record.source_class,
        license_type=record.license_type,
        decision_reason=record.decision_reason,
        attribution_required=record.attribution_required,
        conditions=conditions,
        verified_at=record.verified_at,
        evidence_reference=record.evidence_reference,
        reviewer=record.reviewer,
        ruleset_version=record.ruleset_version,
    )


@router.get(
    "/{source_id}/rights",
    response_model=RightsEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve current rights evaluation record for a source",
)
def get_source_rights(
    source_id: str,
    session: Annotated[Session, Depends(get_db)],
) -> RightsEvaluationResponse:
    """Fetch rights record for an existing source."""
    source = SourceRepository.get_by_id(session, source_id)
    if not source:
        raise NotFoundError("Source", source_id)

    record = RightsService.get_by_source_id(session, source_id)
    if not record:
        raise NotFoundError("RightsRecord for Source", source_id)

    conditions: List[str] = []
    if record.decision == RightsStatus.CONDITIONAL:
        if record.attribution_required:
            conditions.append("attribution_required")
        if record.license_type == LicenseType.CC_BY_SA:
            conditions.append("share_alike_required")

    return RightsEvaluationResponse(
        source_id=record.source_id,
        rights_status=record.decision,
        workflow_state=source.workflow_state,
        source_class=record.source_class,
        license_type=record.license_type,
        decision_reason=record.decision_reason,
        attribution_required=record.attribution_required,
        conditions=conditions,
        verified_at=record.verified_at,
        evidence_reference=record.evidence_reference,
        reviewer=record.reviewer,
        ruleset_version=record.ruleset_version,
    )
