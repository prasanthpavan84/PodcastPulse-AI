"""Source rights clearance and popularity scoring endpoints."""

from datetime import datetime
from typing import Annotated, Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError, RightsAuthorizationError
from app.core.logging import ctx_request_id, get_logger
from app.database.session import get_db
from app.domain.enums import EvidenceStatus, LicenseType, RightsStatus, SourceClass, WorkflowState
from app.repositories.source_repository import SourceRepository
from app.services.popularity_service import PopularityService
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
    rights_status: Optional[str] = Field(
        default=None, description="Direct status mutation field (prohibited for unprivileged clients)"
    )


class HumanRightsReviewRequest(BaseModel):
    """Payload for human rights review and final authorization decision."""

    decision: RightsStatus = Field(..., description="Final rights decision: APPROVED, BLOCKED, or REVIEW_REQUIRED")
    evidence_status: EvidenceStatus = Field(..., description="Status of the supporting evidence")
    reviewer: str = Field(..., min_length=1, max_length=255, description="Human reviewer username or identifier")
    reviewer_role: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Authorized role: legal_counsel, rights_reviewer, compliance_officer, editor",
    )
    decision_reason: str = Field(
        ..., min_length=1, description="Explicit deterministic explanation for the review decision"
    )
    evidence_reference: Optional[str] = Field(
        default=None, max_length=1024, description="Document URL, contract ID, or affidavit reference"
    )
    evidence_type: Optional[str] = Field(
        default=None, max_length=100, description="Evidence type e.g. contract, license_url, email_consent"
    )
    evidence_timestamp: Optional[datetime] = Field(
        default=None, description="Timestamp of evidence creation/verification"
    )
    expires_at: Optional[datetime] = Field(default=None, description="Expiration date of license or permission")
    project_id: Optional[str] = Field(default=None, max_length=36, description="Optional project binding ID")
    commercial_use: Optional[bool] = Field(default=None, description="Whether commercial use is permitted")
    modification_allowed: Optional[bool] = Field(default=None, description="Whether transformation is permitted")
    attribution_required: Optional[bool] = Field(default=None, description="Whether attribution is required")


class RightsEvaluationResponse(BaseModel):
    """Structured response representing evaluated rights record and workflow state."""

    source_id: str
    rights_status: RightsStatus
    workflow_state: WorkflowState
    source_class: SourceClass
    license_type: LicenseType
    evidence_status: Optional[EvidenceStatus] = None
    project_id: Optional[str] = None
    decision_reason: Optional[str] = None
    attribution_required: bool
    conditions: List[str] = Field(default_factory=list)
    verified_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    evidence_reference: Optional[str] = None
    reviewer: Optional[str] = None
    ruleset_version: str = "1.0.0"


class PopularityCalculationRequest(BaseModel):
    """Payload for requesting popularity scoring."""

    project_id: Optional[str] = Field(default=None, description="Optional project context ID")
    channel_signals: Optional[Dict[str, Any]] = Field(default=None, description="Optional configured channel signals")


class PopularityScoreResponse(BaseModel):
    """Structured response representing a deterministic popularity score snapshot."""

    id: str
    source_id: str
    project_id: Optional[str] = None
    algorithm_version: str
    final_score: float
    component_scores: Dict[str, float]
    missing_inputs: List[str]
    rationale: str
    input_snapshot: Optional[Dict[str, Any]] = None
    scored_at: datetime


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
    # API Mutation Bypass Check: Disallow directly setting rights_status = APPROVED via intake API
    if request_data.rights_status is not None:
        raise RightsAuthorizationError(
            "Direct mutation of rights_status is prohibited. Final rights approvals require "
            "the human review endpoint (/rights/review) with authorized human reviewer credentials."
        )

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
        evidence_status=record.evidence_status,
        project_id=record.project_id,
        decision_reason=record.decision_reason,
        attribution_required=record.attribution_required,
        conditions=conditions,
        verified_at=record.verified_at,
        expires_at=record.expires_at,
        evidence_reference=record.evidence_reference,
        reviewer=record.reviewer,
        ruleset_version=record.ruleset_version,
    )


@router.post(
    "/{source_id}/rights/review",
    response_model=RightsEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit authorized human rights review decision",
)
def human_review_source_rights(
    source_id: str,
    review_data: HumanRightsReviewRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> RightsEvaluationResponse:
    """Execute transactional human rights clearance decision with audit logging."""
    req_id = ctx_request_id.get() or request.headers.get("X-Request-ID")

    record = RightsService.record_human_decision(
        session=session,
        source_id=source_id,
        decision=review_data.decision,
        evidence_status=review_data.evidence_status,
        reviewer=review_data.reviewer,
        reviewer_role=review_data.reviewer_role,
        decision_reason=review_data.decision_reason,
        evidence_reference=review_data.evidence_reference,
        evidence_type=review_data.evidence_type,
        evidence_timestamp=review_data.evidence_timestamp,
        expires_at=review_data.expires_at,
        project_id=review_data.project_id,
        commercial_use=review_data.commercial_use,
        modification_allowed=review_data.modification_allowed,
        attribution_required=review_data.attribution_required,
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
        evidence_status=record.evidence_status,
        project_id=record.project_id,
        decision_reason=record.decision_reason,
        attribution_required=record.attribution_required,
        conditions=conditions,
        verified_at=record.verified_at,
        expires_at=record.expires_at,
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
        evidence_status=record.evidence_status,
        project_id=record.project_id,
        decision_reason=record.decision_reason,
        attribution_required=record.attribution_required,
        conditions=conditions,
        verified_at=record.verified_at,
        expires_at=record.expires_at,
        evidence_reference=record.evidence_reference,
        reviewer=record.reviewer,
        ruleset_version=record.ruleset_version,
    )


@router.post(
    "/{source_id}/popularity",
    response_model=PopularityScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate and persist popularity score for a source",
)
def calculate_source_popularity(
    source_id: str,
    request_data: PopularityCalculationRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
) -> PopularityScoreResponse:
    """Calculate deterministic popularity_v1 score, record snapshot, and return result."""
    req_id = ctx_request_id.get() or request.headers.get("X-Request-ID")

    score_record = PopularityService.calculate_and_record(
        session=session,
        source_id=source_id,
        project_id=request_data.project_id,
        channel_signals=request_data.channel_signals,
        request_id=req_id,
    )

    session.commit()

    return PopularityScoreResponse(
        id=score_record.id,
        source_id=score_record.source_id,
        project_id=score_record.project_id,
        algorithm_version=score_record.algorithm_version,
        final_score=score_record.final_score,
        component_scores=score_record.component_scores or {},
        missing_inputs=score_record.missing_inputs or [],
        rationale=score_record.rationale,
        input_snapshot=score_record.input_snapshot,
        scored_at=score_record.scored_at,
    )


@router.get(
    "/{source_id}/popularity",
    response_model=PopularityScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve latest popularity score for a source",
)
def get_source_popularity(
    source_id: str,
    session: Annotated[Session, Depends(get_db)],
) -> PopularityScoreResponse:
    """Fetch latest popularity score record for a source."""
    source = SourceRepository.get_by_id(session, source_id)
    if not source:
        raise NotFoundError("Source", source_id)

    score_record = PopularityService.get_latest_score(session, source_id)
    if not score_record:
        raise NotFoundError("PopularityScore for Source", source_id)

    return PopularityScoreResponse(
        id=score_record.id,
        source_id=score_record.source_id,
        project_id=score_record.project_id,
        algorithm_version=score_record.algorithm_version,
        final_score=score_record.final_score,
        component_scores=score_record.component_scores or {},
        missing_inputs=score_record.missing_inputs or [],
        rationale=score_record.rationale,
        input_snapshot=score_record.input_snapshot,
        scored_at=score_record.scored_at,
    )
