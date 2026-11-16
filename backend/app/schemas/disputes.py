from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator, ConfigDict

class DisputeCreate(BaseModel):
    entity_type: str = Field(..., description="One of: ledger_entry, payment_request, tenancy, reliability_score, ric_application, household, certificate")
    entity_id: UUID = Field(..., description="ID of the entity being disputed")
    reason: str = Field(..., min_length=1)

class DisputeReviewStatus(str, Enum):
    under_review = "under_review"
    resolved = "resolved"
    rejected = "rejected"

class DisputeReview(BaseModel):
    status: DisputeReviewStatus
    resolution_note: Optional[str] = None

    @validator("resolution_note")
    def note_required_for_resolved_or_rejected(cls, v, values):
        if values.get("status") in {DisputeReviewStatus.resolved, DisputeReviewStatus.rejected} and not v:
            raise ValueError("resolution_note is required when status is resolved or rejected")
        return v

class DisputeResponse(BaseModel):
    id: UUID
    raised_by: UUID
    entity_type: str
    entity_id: UUID
    reason: str
    status: str
    resolution_note: Optional[str] = None
    resolved_by: Optional[UUID] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
