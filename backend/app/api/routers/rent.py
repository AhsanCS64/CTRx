"""Monthly rent system.

Built on the existing ``tenancies``, ``payment_requests`` and ``ledger_entries``
tables. A monthly rent invoice is a ``payment_requests`` row whose
``period_month`` is the first day of the billed month. When the tenant pays it,
the tenant reports the payment; the landlord confirms receipt before a ledger
entry is created.

Endpoints
---------
- ``GET  /rent/overview``            → tenant's current home + this month status
- ``GET  /rent/tenancies``           → landlord's active tenancies + invoice state
- ``POST /rent/{tenancy_id}/invoice``→ landlord raises this month's rent invoice
- ``POST /rent/invoices/{id}/pay``   → tenant reports payment
- ``POST /rent/invoices/{id}/confirm`` → landlord confirms receipt
- ``GET  /rent/history``             → invoice history for the caller
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func as sa_func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.ledger_entries import LedgerEntry
from app.db.models.payment_requests import PaymentRequest
from app.db.models.properties import Property
from app.db.models.tenancies import Tenancy
from app.db.models.tenant_profiles import TenantProfile
from app.db.models.users import User
from app.schemas.payments import PaymentRequestCreate
from app.schemas.rent import (
    LandlordRentRow,
    RentInvoice,
    RentInvoiceCreate,
    RentOverview,
    RentPaymentSubmission,
)
from app.services.payments import (
    confirm_payment_receipt,
    create_payment_request,
    submit_payment_report,
)

router = APIRouter(prefix="/rent", tags=["rent"])


def _current_period() -> date:
    today = date.today()
    return date(today.year, today.month, 1)


def _as_uuid(value: str) -> UUID:
    try:
        return UUID(str(value))
    except (ValueError, AttributeError, TypeError) as exc:
        raise HTTPException(status_code=404, detail="Record not found") from exc


def _invoice(pr: PaymentRequest) -> RentInvoice:
    return RentInvoice(
        id=pr.id,
        amount=pr.amount,
        status=pr.status,
        period_month=pr.period_month,
        description=pr.description,
        created_at=pr.created_at,
        paid_on=pr.paid_on,
        payment_method=pr.payment_method,
        note=pr.note,
    )


@router.get("/overview", response_model=RentOverview)
def rent_overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")

    row = db.execute(
        select(Tenancy, Property)
        .join(Property, Tenancy.property_id == Property.id)
        .where(Tenancy.tenant_id == user.id, Tenancy.status == "active")
        .order_by(Tenancy.start_date.desc())
    ).first()
    if not row:
        return RentOverview(active=False)

    tenancy, prop = row
    period = _current_period()

    invoice = db.execute(
        select(PaymentRequest)
        .where(
            PaymentRequest.tenancy_id == tenancy.id,
            PaymentRequest.period_month == period,
        )
        .order_by(PaymentRequest.created_at.desc())
    ).scalars().first()

    total_paid = db.execute(
        select(sa_func.coalesce(sa_func.sum(LedgerEntry.amount), 0)).where(
            LedgerEntry.tenancy_id == tenancy.id,
            LedgerEntry.entry_type == "payment",
        )
    ).scalar() or Decimal("0")

    paid_current = db.execute(
        select(sa_func.count())
        .select_from(LedgerEntry)
        .where(
            LedgerEntry.tenancy_id == tenancy.id,
            LedgerEntry.period_month == period,
            LedgerEntry.entry_type == "payment",
        )
    ).scalar() or 0

    rent = Decimal(str(tenancy.rent))
    return RentOverview(
        active=True,
        tenancy_id=tenancy.id,
        tenant_id=tenancy.tenant_id,
        property_address=prop.address_line,
        property_type=prop.property_type,
        monthly_rent=rent,
        deposit=Decimal(str(tenancy.deposit)),
        rent_due_day=tenancy.rent_due_day,
        start_date=tenancy.start_date,
        period_month=period,
        invoice=_invoice(invoice) if invoice else None,
        paid_current_period=bool(paid_current),
        total_paid=Decimal(str(total_paid)),
        outstanding=Decimal("0") if paid_current else rent,
    )


@router.get("/tenancies", response_model=list[LandlordRentRow])
def landlord_rent(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")

    period = _current_period()
    rows = db.execute(
        select(Tenancy, Property, TenantProfile)
        .join(Property, Tenancy.property_id == Property.id)
        .outerjoin(TenantProfile, Tenancy.tenant_id == TenantProfile.user_id)
        .where(Tenancy.landlord_id == user.id, Tenancy.status == "active")
        .order_by(Tenancy.start_date.desc())
    ).all()

    result: list[LandlordRentRow] = []
    for tenancy, prop, tenant in rows:
        invoice = db.execute(
            select(PaymentRequest)
            .where(
                PaymentRequest.tenancy_id == tenancy.id,
                PaymentRequest.period_month == period,
            )
            .order_by(PaymentRequest.created_at.desc())
        ).scalars().first()
        result.append(
            LandlordRentRow(
                tenancy_id=tenancy.id,
                tenant_id=tenancy.tenant_id,
                tenant_name=tenant.full_name if tenant else None,
                property_address=prop.address_line,
                monthly_rent=Decimal(str(tenancy.rent)),
                rent_due_day=tenancy.rent_due_day,
                period_month=period,
                invoice_id=invoice.id if invoice else None,
                invoice_status=invoice.status if invoice else "none",
                payment_method=invoice.payment_method if invoice else None,
                payment_note=invoice.note if invoice else None,
                paid_on=invoice.paid_on if invoice else None,
            )
        )
    return result


@router.post("/{tenancy_id}/invoice", response_model=RentInvoice)
def generate_invoice(
    tenancy_id: str,
    payload: RentInvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")

    tenancy = db.execute(
        select(Tenancy).where(
            Tenancy.id == _as_uuid(tenancy_id), Tenancy.landlord_id == user.id
        )
    ).scalar_one_or_none()
    if not tenancy:
        raise HTTPException(status_code=404, detail="Tenancy not found")
    if tenancy.status != "active":
        raise HTTPException(status_code=409, detail="Only active tenancies can be billed")

    period = payload.period_month or _current_period()
    period = date(period.year, period.month, 1)

    existing = db.execute(
        select(PaymentRequest)
        .where(
            PaymentRequest.tenancy_id == tenancy.id,
            PaymentRequest.period_month == period,
        )
        .order_by(PaymentRequest.created_at.desc())
    ).scalars().first()
    if existing:
        return _invoice(existing)

    amount = payload.amount or Decimal(str(tenancy.rent))
    description = payload.description or f"Monthly rent for {period.strftime('%B %Y')}"
    due_day = min(tenancy.rent_due_day, monthrange(period.year, period.month)[1])
    due_date = date(period.year, period.month, due_day)
    pr = create_payment_request(
        db,
        landlord_user_id=user.id,
        payload=PaymentRequestCreate(
            tenancy_id=tenancy.id,
            amount=amount,
            period_month=period,
            paid_on=due_date,
            description=description,
        ),
        role="landlord",
    )
    return _invoice(pr)


@router.post("/invoices/{invoice_id}/pay", response_model=RentInvoice)
def pay_invoice(
    invoice_id: str,
    payload: RentPaymentSubmission,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")

    pr = submit_payment_report(
        db,
        tenant_user_id=user.id,
        request_id=_as_uuid(invoice_id),
        payment_method=payload.payment_method,
        note=payload.note,
        paid_on=payload.paid_on,
    )
    return _invoice(pr)


@router.post("/invoices/{invoice_id}/confirm", response_model=RentInvoice)
def confirm_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")
    pr = confirm_payment_receipt(db, user.id, _as_uuid(invoice_id))
    return _invoice(pr)


@router.get("/history", response_model=list[RentInvoice])
def rent_history(
    tenancy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(PaymentRequest).join(
        Tenancy, PaymentRequest.tenancy_id == Tenancy.id
    )
    if user.role == "tenant":
        stmt = stmt.where(Tenancy.tenant_id == user.id)
    elif user.role == "landlord":
        stmt = stmt.where(Tenancy.landlord_id == user.id)
    else:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted")

    if tenancy_id:
        stmt = stmt.where(PaymentRequest.tenancy_id == _as_uuid(tenancy_id))

    stmt = stmt.order_by(PaymentRequest.period_month.desc(), PaymentRequest.created_at.desc())
    return [_invoice(pr) for pr in db.scalars(stmt).all()]
