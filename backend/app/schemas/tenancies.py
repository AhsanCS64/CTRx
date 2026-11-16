"""Pydantic schemas for tenancy management.

The schemas mirror the SQLAlchemy model defined in
`backend/app/db/models/tenancies.py`. All timestamps are handled as
Python ``datetime`` objects which FastAPI will serialize to ISO‑8601
strings.
"""

from datetime import date, datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel, Field, validator, ConfigDict


class TenancyCreateRequest(BaseModel):
    property_id: str = Field(..., description="UUID of the property to lease")
    tenant_id: str = Field(..., description="UUID of the tenant (user) profile")
    start_date: date = Field(..., description="Lease start date")
    end_date: Optional[date] = Field(None, description="Optional lease end date")
    rent: float = Field(..., gt=0, description="Monthly rent amount")
    deposit: float = Field(..., gt=0, description="Security deposit amount")
    rent_due_day: int = Field(..., ge=1, le=31, description="Day of month rent is due")

    @validator("end_date")
    def end_after_start(cls, v, values):
        if v and "start_date" in values and v < values["start_date"]:
            raise ValueError("end_date must be on or after start_date")
        return v


class TenancyUpdateStatusRequest(BaseModel):
    status: str = Field(..., description="One of: ended, terminated")
    end_date: Optional[date] = Field(None, description="Actual termination date if differs from planned")

    @validator("status")
    def validate_status(cls, v):
        if v not in {"ended", "terminated"}:
            raise ValueError("status must be 'ended' or 'terminated'")
        return v


class TenancyResponse(BaseModel):
    id: UUID
    property_id: UUID
    tenant_id: UUID
    landlord_id: UUID
    start_date: date
    end_date: Optional[date]
    rent: float
    deposit: float
    rent_due_day: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    property_address: Optional[str] = None
    property_type: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class TenancyListResponse(BaseModel):
    total: int
    items: List[TenancyResponse]
