"""Pydantic schemas for Payments and Ledger endpoints."""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, condecimal


# ---------------------------------------------------------------------------
# Payment Request schemas
# ---------------------------------------------------------------------------

class PaymentRequestCreate(BaseModel):
    tenancy_id: UUID
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    period_month: date
    paid_on: Optional[date] = None
    description: Optional[str] = None


class PaymentRequestDecide(BaseModel):
    decision: str = Field(..., pattern="^(accepted|rejected|cancelled)$")
    rejection_reason: Optional[str] = None
    payment_method: Optional[str] = Field(None, max_length=80)
    note: Optional[str] = Field(None, max_length=500)


class PaymentRequestResponse(BaseModel):
    id: UUID
    tenancy_id: UUID
    requested_by: UUID
    amount: Decimal
    period_month: date
    description: Optional[str]
    status: str
    decided_by: Optional[UUID]
    decided_at: Optional[datetime]
    rejection_reason: Optional[str]
    paid_on: date
    payment_method: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Ledger / Correction schemas
# ---------------------------------------------------------------------------

class CorrectionCreate(BaseModel):
    tenancy_id: UUID
    amount: Decimal = Field(..., ne=0, decimal_places=2)
    period_month: date
    corrects_entry_id: Optional[UUID] = None
    correction_reason: str
    paid_on: Optional[date] = None


class LedgerEntryResponse(BaseModel):
    id: UUID
    tenancy_id: UUID
    entry_type: str
    amount: Decimal
    payment_request_id: Optional[UUID]
    corrects_entry_id: Optional[UUID]
    correction_reason: Optional[str]
    period_month: date
    paid_on: Optional[date]
    created_by: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class LedgerWithBalance(BaseModel):
    entries: List[LedgerEntryResponse]
    running_balance: Decimal
