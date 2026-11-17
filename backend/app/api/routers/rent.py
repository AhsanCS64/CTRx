"""Monthly rent system.

Built on the existing ``tenancies``, ``payment_requests`` and ``ledger_entries``
tables. A monthly rent invoice is a ``payment_requests`` row whose
``period_month`` is the first day of the billed month. When the tenant pays it,
the tenant reports the payment; the landlord confirms receipt before a ledger
entry is created.

Endpoints
---------
- ``GET  /rent/overview``            â†’ tenant's current home + this month status
- ``GET  /rent/tenancies``           â†’ landlord's active tenancies + invoice state
- ``POST /rent/{tenancy_id}/invoice``â†’ landlord raises this month's rent invoice
- ``POST /rent/invoices/{id}/pay``   â†’ tenant reports payment
- ``POST /rent/invoices/{id}/confirm`` â†’ landlord confirms receipt
- ``GET  /rent/history``             â†’ invoice history for the caller
"""

import base64
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Response, status
from reportlab.pdfgen import canvas
from sqlalchemy import func as sa_func, select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.landlord_profiles import LandlordProfile
from app.db.models.ledger_entries import LedgerEntry
from app.db.models.payment_requests import PaymentRequest
from app.db.models.properties import Property
from app.db.models.property_units import PropertyUnit
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

from app.services.scoring import MISSED_POINTS, reliability_history, score_for_events

router = APIRouter(prefix="/rent", tags=["rent"])
DHAKA = ZoneInfo("Asia/Dhaka")


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
        select(Tenancy, Property, PropertyUnit.unit_number)
        .join(Property, Tenancy.property_id == Property.id)
        .outerjoin(PropertyUnit, PropertyUnit.id == Tenancy.unit_id)
        .where(Tenancy.tenant_id == user.id, Tenancy.status == "active")
        .order_by(Tenancy.start_date.desc())
    ).first()
    if not row:
        return RentOverview(active=False)

    tenancy, prop, unit_number = row
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
        unit_number=unit_number,
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


def _missed_eligible(invoice: PaymentRequest, tenancy: Tenancy) -> bool:
    period = invoice.period_month
    due = period.replace(day=min(tenancy.rent_due_day, monthrange(period.year, period.month)[1]))
    issued = invoice.created_at.astimezone(DHAKA).date()
    return (
        invoice.status == "pending"
        and invoice.requested_by == tenancy.landlord_id
        and max(due, issued) < datetime.now(DHAKA).date()
    )


@router.get("/tenancies", response_model=list[LandlordRentRow])
def landlord_rent(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")

    period = _current_period()
    rows = db.execute(
        select(Tenancy, Property, TenantProfile, PropertyUnit.unit_number)
        .join(Property, Tenancy.property_id == Property.id)
        .outerjoin(PropertyUnit, PropertyUnit.id == Tenancy.unit_id)
        .outerjoin(TenantProfile, Tenancy.tenant_id == TenantProfile.user_id)
        .where(Tenancy.landlord_id == user.id, Tenancy.status == "active")
        .order_by(Tenancy.start_date.desc())
    ).all()

    missed_ids = set(db.execute(text("""
        SELECT e.tenancy_id
        FROM reliability_score_events e JOIN tenancies t ON t.id = e.tenancy_id
        WHERE t.landlord_id = :landlord AND e.event_type = 'missed' AND e.period_month = :period
    """), {"landlord": user.id, "period": period}).scalars())
    result: list[LandlordRentRow] = []
    for tenancy, prop, tenant, unit_number in rows:
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
                unit_number=unit_number,
                monthly_rent=Decimal(str(tenancy.rent)),
                rent_due_day=tenancy.rent_due_day,
                period_month=period,
                invoice_id=invoice.id if invoice else None,
                invoice_status=invoice.status if invoice else "none",
                missed_recorded=tenancy.id in missed_ids,
                can_record_missed=bool(invoice and tenancy.id not in missed_ids and _missed_eligible(invoice, tenancy)),
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


@router.post("/invoices/{invoice_id}/missed", status_code=201)
def record_missed_rent(
    invoice_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "landlord":
        raise HTTPException(403, "Landlord role required")
    row = db.execute(
        select(PaymentRequest, Tenancy)
        .join(Tenancy, Tenancy.id == PaymentRequest.tenancy_id)
        .where(PaymentRequest.id == invoice_id, Tenancy.landlord_id == user.id)
        .with_for_update(of=PaymentRequest)
    ).one_or_none()
    if row is None:
        raise HTTPException(404, "Invoice not found")
    invoice, tenancy = row
    if not _missed_eligible(invoice, tenancy):
        raise HTTPException(409, "Only overdue, unreported rent invoices can be recorded as missed")

    tenant = db.get(TenantProfile, tenancy.tenant_id, with_for_update=True)
    if tenant is None:
        raise HTTPException(409, "The tenancy has no tenant profile")
    params = {"tenancy": tenancy.id, "period": invoice.period_month, "tenant": tenancy.tenant_id}
    existing = db.execute(text("""
        SELECT 1 FROM reliability_score_events
        WHERE tenancy_id = :tenancy AND period_month = :period AND event_type = 'missed'
    """), params).scalar()
    if existing:
        raise HTTPException(409, "Missed rent is already recorded for this period")
    payment = db.execute(text("""
        SELECT COALESCE(sum(amount), 0) FROM ledger_entries
        WHERE tenancy_id = :tenancy AND period_month = :period
    """), params).scalar_one()
    if payment > 0:
        raise HTTPException(409, "Confirmed rent is already recorded for this period")

    history = reliability_history(db, tenancy.tenant_id)
    score = score_for_events([*history["events"], {"points": MISSED_POINTS}])
    snapshot_id = db.execute(text("""
        INSERT INTO reliability_scores (tenant_id, score, has_history, model_version)
        VALUES (:tenant, :score, true, 'v2') RETURNING id
    """), {**params, "score": score}).scalar_one()
    db.execute(text("""
        INSERT INTO reliability_score_events (score_id, tenancy_id, period_month, event_type, points_delta, description)
        VALUES (:snapshot, :tenancy, :period, 'missed', :points, 'Missed rent recorded by landlord')
    """), {**params, "snapshot": snapshot_id, "points": MISSED_POINTS})
    db.execute(text("""
        INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
        VALUES (:tenant, 'reliability', :invoice, :message)
    """), {**params, "invoice": invoice_id,
           "message": f"Your landlord recorded missed rent for {invoice.period_month:%B %Y} ({MISSED_POINTS} reliability points)."})
    log_action(db, "rent.missed", user.id, user.role, "payment_request", invoice_id)
    db.commit()
    return {"score": score}


@router.get("/invoices/{invoice_id}/receipt")
def rent_receipt(
    invoice_id: UUID,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in ("tenant", "landlord"):
        raise HTTPException(status_code=403, detail="Not permitted")
    owner = Tenancy.tenant_id if user.role == "tenant" else Tenancy.landlord_id
    record = db.execute(
        select(LedgerEntry, Property.address_line, PropertyUnit.unit_number)
        .join(Tenancy, Tenancy.id == LedgerEntry.tenancy_id)
        .join(Property, Property.id == Tenancy.property_id)
        .outerjoin(PropertyUnit, PropertyUnit.id == Tenancy.unit_id)
        .join(PaymentRequest, PaymentRequest.id == LedgerEntry.payment_request_id)
        .where(
            owner == user.id,
            PaymentRequest.id == invoice_id,
            PaymentRequest.status == "accepted",
            LedgerEntry.entry_type == "payment",
        )
    ).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="A confirmed receipt is unavailable")

    entry, residence, unit_number = record

    output = BytesIO()
    pdf = canvas.Canvas(output)
    pdf.setTitle("CTRx Rent Payment Receipt")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(48, 770, "CTRx Rent Payment Receipt")
    lines = pdf.beginText(48, 732)
    lines.setFont("Helvetica", 11)
    for line in (
        f"Receipt ID: {entry.id}",
        f"Invoice ID: {invoice_id}",
        f"Residence: {residence}",
        *((f"Apartment: {unit_number}",) if unit_number else ()),
        f"Rent period: {entry.period_month:%B %Y}",
        f"Recorded payment date: {entry.paid_on:%d %B %Y}",
        f"Confirmed payment: BDT {entry.amount:,.2f}",
    ):
        lines.textLine(line)
    pdf.drawText(lines)
    pdf.save()
    response.headers["Cache-Control"] = "no-store"
    return {
        "filename": f"rent-receipt-{invoice_id}.pdf",
        "content_base64": base64.b64encode(output.getvalue()).decode("ascii"),
    }


@router.get("/history", response_model=list[RentInvoice])
def rent_history(
    tenancy_id: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(PaymentRequest, Property.address_line, TenantProfile.full_name, LandlordProfile.full_name, PropertyUnit.unit_number)
        .join(Tenancy, PaymentRequest.tenancy_id == Tenancy.id)
        .join(Property, Property.id == Tenancy.property_id)
        .outerjoin(PropertyUnit, PropertyUnit.id == Tenancy.unit_id)
        .outerjoin(TenantProfile, TenantProfile.user_id == Tenancy.tenant_id)
        .outerjoin(LandlordProfile, LandlordProfile.user_id == Tenancy.landlord_id)
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
    return [
        _invoice(invoice).model_copy(update={
            "property_address": address,
            "unit_number": unit_number,
            "tenant_name": tenant_name,
            "landlord_name": landlord_name,
        })
        for invoice, address, tenant_name, landlord_name, unit_number in db.execute(stmt).all()
    ]
