"""Pydantic schemas for the monthly rent system."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RentInvoice(BaseModel):
    """A single monthly rent invoice (backed by ``payment_requests``)."""

    id: UUID
    amount: Decimal
    status: str
    period_month: date
    description: Optional[str] = None
    created_at: datetime
    paid_on: date
    payment_method: Optional[str] = None
    note: Optional[str] = None
    tenant_name: Optional[str] = None
    landlord_name: Optional[str] = None
    unit_number: Optional[str] = None
    property_address: Optional[str] = None


class RentInvoiceCreate(BaseModel):
    period_month: Optional[date] = Field(None, description="Defaults to the current month")
    amount: Optional[Decimal] = Field(None, gt=0, description="Defaults to the tenancy rent")
    description: Optional[str] = None


class RentOverview(BaseModel):
    active: bool
    tenancy_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None
    unit_number: Optional[str] = None
    property_address: Optional[str] = None
    property_type: Optional[str] = None
    monthly_rent: Optional[Decimal] = None
    deposit: Optional[Decimal] = None
    rent_due_day: Optional[int] = None
    start_date: Optional[date] = None
    period_month: Optional[date] = None
    invoice: Optional[RentInvoice] = None
    paid_current_period: bool = False
    total_paid: Decimal = Decimal("0")
    outstanding: Decimal = Decimal("0")


class LandlordRentRow(BaseModel):
    tenancy_id: UUID
    tenant_id: UUID
    tenant_name: Optional[str] = None
    unit_number: Optional[str] = None
    property_address: Optional[str] = None
    monthly_rent: Decimal
    rent_due_day: int
    period_month: date
    invoice_id: Optional[UUID] = None
    invoice_status: str = "none"
    missed_recorded: bool = False
    can_record_missed: bool = False
    payment_method: Optional[str] = None
    payment_note: Optional[str] = None
    paid_on: Optional[date] = None


class RentPaymentSubmission(BaseModel):
    payment_method: str = Field(..., min_length=1, max_length=80)
    note: Optional[str] = Field(None, max_length=500)
    paid_on: Optional[date] = None
