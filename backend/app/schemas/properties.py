"""Pydantic schemas for property and listing domain.

These are placeholders – fields are based on the DB schema but without
business logic. Each schema includes a ``# TODO: FR-xx`` comment referencing the
corresponding Software Requirement Specification item.
"""

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PropertyBase(BaseModel):
    area_id: int
    address_line: str = Field(..., min_length=5, max_length=500)
    property_type: str
    monthly_rent: float = Field(..., gt=0)
    floor_area_sqft: float = Field(..., gt=0)
    bedrooms: int = Field(..., ge=0, le=50)
    bathrooms: int = Field(..., ge=0, le=50)
    floor_number: int = Field(..., ge=0)
    available_from: date

class PropertyCreate(PropertyBase):
    pass

class PropertyResponse(PropertyBase):
    id: UUID
    landlord_id: UUID
    created_at: datetime
    updated_at: datetime
    area_name: Optional[str] = None
    district: Optional[str] = None
    division: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

class ListingBase(BaseModel):
    property_id: Optional[UUID] = None
    status: Optional[str] = "draft"
    title: Optional[str] = Field(None, max_length=160)
    description: Optional[str] = None
    published_at: Optional[datetime] = None

class ListingCreate(ListingBase):
    status: Literal["draft", "available"] = "draft"

class ListingResponse(ListingBase):
    id: UUID
    unit_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class AvailableListingResponse(ListingResponse):
    area_id: int
    area_name: str
    district: str
    division: str
    property_address: str
    property_type: str
    monthly_rent: float
    floor_area_sqft: float
    bedrooms: int
    bathrooms: int
    floor_number: int
    unit_number: Optional[str] = None


class PropertyUnitCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    unit_number: str = Field(..., min_length=1, max_length=40)
    floor_number: int = Field(0, ge=0)
    monthly_rent: float = Field(..., gt=0)
    floor_area_sqft: float = Field(..., gt=0)
    bedrooms: int = Field(0, ge=0, le=50)
    bathrooms: int = Field(0, ge=0, le=50)
    available_from: date
    status: str = Field("available", pattern="^(available|occupied|maintenance)$")


class PropertyUnitResponse(PropertyUnitCreate):
    id: UUID
    property_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
