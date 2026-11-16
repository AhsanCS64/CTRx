from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, Field, ConfigDict

class ViewingCreateRequest(BaseModel):
    listing_id: str = Field(..., description="UUID of the listing to view")
    proposed_time: AwareDatetime = Field(..., description="Proposed datetime for the viewing")
    message: Optional[str] = Field(None, description="Optional message to the landlord")

class ViewingResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    listing_id: UUID
    proposed_time: datetime
    message: Optional[str] = None
    status: str
    expires_at: datetime
    confirmed_time: Optional[datetime] = None
    alternative_time: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    property_address: Optional[str] = None
    property_type: Optional[str] = None
    unit_number: Optional[str] = None
    monthly_rent: Optional[float] = None
    listing_title: Optional[str] = None
    landlord_name: Optional[str] = None
    tenant_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class ViewingCounterProposal(BaseModel):
    new_time: datetime = Field(..., description="Counter-proposed datetime")
    message: Optional[str] = None

class ViewingStatusUpdate(BaseModel):
    status: str = Field(..., description="One of: confirmed, declined, countered, cancelled")
    alternative_time: AwareDatetime | None = None

class ViewingListResponse(BaseModel):
    total: int
    items: List[ViewingResponse]
