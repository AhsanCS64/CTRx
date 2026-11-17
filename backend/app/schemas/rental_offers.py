"""Pydantic schemas for rental offers and price negotiation."""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RentalOfferCreate(BaseModel):
    listing_id: str = Field(..., description="UUID of the listing to make an offer on")
    proposed_rent: float = Field(..., gt=0, description="Monthly rent the tenant offers")
    move_in_date: date = Field(..., description="Proposed move-in date")
    message: Optional[str] = Field(None, description="Optional message to the landlord")


class RentalOfferAction(BaseModel):
    action: str = Field(..., description="One of: accept, reject, counter")
    response_message: Optional[str] = Field(None, description="Landlord's or tenant's response notes")
    counter_rent: Optional[float] = Field(None, gt=0, description="Counter-offer rent amount")


class RentalOfferResponse(BaseModel):
    id: UUID
    listing_id: UUID
    tenant_id: UUID
    landlord_id: UUID
    proposed_rent: float
    counter_rent: Optional[float]
    status: str
    move_in_date: date
    message: Optional[str]
    landlord_response: Optional[str]
    tenant_response: Optional[str]
    expires_at: datetime
    responded_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    property_address: Optional[str] = None
    listing_title: Optional[str] = None
    unit_number: Optional[str] = None
    landlord_name: Optional[str] = None
    tenant_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)