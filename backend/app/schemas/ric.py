"""Pydantic schemas for RIC application and government review.

- ``RicApplicationCreate``: payload for submitting a new RIC application.
- ``RicApplicationResponse``: information returned for an application (status, timestamps, notes).
- ``GovernmentReviewRequest``: action taken by a government official (approve/forward/reject) with optional note.
- ``VerificationResponse``: fields returned by the public verification endpoint.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, validator


class ApplicationMemberCreate(BaseModel):
    full_name: str
    relationship: Optional[str] = None
    date_of_birth: Optional[datetime] = None


class RicApplicationCreate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: str
    identity_number: Optional[str] = Field(None, min_length=4, max_length=64)
    identity_number_enc: Optional[str] = Field(
        None, description="Base64‑encoded encrypted identity number."
    )
    identity_number_hmac: Optional[str] = None
    identity_last4: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    permanent_address: Optional[str] = None
    household_address: str
    area_id: int
    previous_ric_id: Optional[str] = None
    members: List[ApplicationMemberCreate] = Field(default_factory=list, max_length=20)

    @validator("identity_last4")
    def validate_last4(cls, v):
        if v and len(v) != 4:
            raise ValueError("identity_last4 must be exactly 4 characters")
        return v

    @validator("identity_number_hmac", always=True)
    def validate_identity_fields(cls, v, values):
        if not v and not values.get("identity_number"):
            raise ValueError("identity_number is required")
        return v

class RelocationRequest(BaseModel):
    household_address: str = Field(..., min_length=5, max_length=1000)
    area_id: int
    permanent_address: Optional[str] = None

class RicApplicationResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    applicant_name: Optional[str] = None
    status: str
    area_id: int
    area_name: Optional[str] = None
    submitted_at: datetime
    local_reviewed_by: Optional[UUID]
    local_reviewed_at: Optional[datetime]
    central_reviewed_by: Optional[UUID]
    central_reviewed_at: Optional[datetime]
    local_note: Optional[str] = None
    central_note: Optional[str] = None
    rejection_reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)

class GovernmentReviewRequest(BaseModel):
    action: str = Field(..., description="One of: approve, forward, reject, return_to_local")
    note: Optional[str] = Field(None, max_length=2000)

    @validator("action")
    def validate_action(cls, v):
        allowed = {"approve", "forward", "reject", "return_to_local"}
        if v not in allowed:
            raise ValueError(f"action must be one of {allowed}")
        return v

class VerificationResponse(BaseModel):
    ric_number: str
    status: str
    issued_at: datetime
    expires_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
