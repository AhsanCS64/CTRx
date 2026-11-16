"""Service functions for Payments, Ledger, and Corrections.

Business rules
--------------
- Only a landlord (role='landlord') may create a payment request.
- A user may NOT decide their own payment request (403).
- Pending requests can be reported/declined; submitted requests await landlord confirmation.
- A tenant payment report is not a ledger entry; only landlord confirmation records it.
- Ledger entries are append-only; never call db.delete() on them.
- IntegrityError containing 'forbid_mutation' → HTTP 409 ERR_LEDGER_IMMUTABLE.
- Duplicate payment_request_id in ledger → HTTP 409 ERR_PAYMENT_ALREADY_IN_LEDGER.
- All state-changing operations emit an audit log entry.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db.models.payment_requests import PaymentRequest
from app.db.models.ledger_entries import LedgerEntry
from app.db.models.tenancies import Tenancy
from app.schemas.payments import (
    CorrectionCreate,
    LedgerEntryResponse,
    LedgerWithBalance,
    PaymentRequestCreate,
    PaymentRequestDecide,
    PaymentRequestResponse,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _map_integrity_error(e: IntegrityError) -> HTTPException:
    msg = str(e.orig) if e.orig else str(e)
    if "forbid_mutation" in msg:
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ERR_LEDGER_IMMUTABLE",
        )
    if "ledger_entries_payment_request_id_key" in msg or "unique" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ERR_PAYMENT_ALREADY_IN_LEDGER",
        )
    raise e


# ---------------------------------------------------------------------------
# Payment Requests
# ---------------------------------------------------------------------------

def create_payment_request(
    db: Session,
    landlord_user_id: UUID,
    payload: PaymentRequestCreate,
    role: str = "landlord",
) -> PaymentRequest:
    """Insert a new payment request (landlord only)."""
    pr = PaymentRequest(
        tenancy_id=payload.tenancy_id,
        requested_by=landlord_user_id,
        amount=payload.amount,
        period_month=payload.period_month,
        paid_on=payload.paid_on or payload.period_month,
        description=payload.description,
        status="pending",
    )
    db.add(pr)
    db.flush()
    log_action(
        db,
        action="payment_request.create",
        actor_id=str(landlord_user_id),
        actor_role=role,
        entity_type="payment_request",
        entity_id=str(pr.id),
        metadata={"amount": str(payload.amount), "period_month": str(payload.period_month)},
    )
    db.commit()
    db.refresh(pr)
    return pr


def decide_payment_request(
    db: Session,
    decider_user_id: UUID,
    request_id: UUID,
    payload: PaymentRequestDecide,
    role: str = "tenant",
) -> PaymentRequest:
    """Report payment or reject/cancel a pending payment request.

    - Decider cannot be the original requester (403).
    - Only 'pending' requests can be decided (409).
    - Tenant acceptance records a report, never a ledger entry.
    """
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found")

    if role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    tenancy = db.get(Tenancy, pr.tenancy_id)
    if tenancy is None or str(tenancy.tenant_id) != str(decider_user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your payment request")

    if payload.decision == "accepted":
        return submit_payment_report(
            db,
            tenant_user_id=decider_user_id,
            request_id=pr.id,
            payment_method=payload.payment_method or "Reported by tenant",
            note=payload.note,
        )

    if str(pr.requested_by) == str(decider_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requester cannot decide their own payment request",
        )

    if pr.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Payment request has already been decided",
        )

    if payload.decision == "rejected":
        if not payload.rejection_reason:
            raise HTTPException(status_code=422, detail="A rejection reason is required")
        pr.rejection_reason = payload.rejection_reason
    pr.status = payload.decision
    pr.decided_by = decider_user_id
    pr.decided_at = datetime.now(timezone.utc)

    log_action(
        db,
        action=f"payment_request.{payload.decision}",
        actor_id=str(decider_user_id),
        actor_role=role,
        entity_type="payment_request",
        entity_id=str(pr.id),
        metadata={"decision": payload.decision, "rejection_reason": payload.rejection_reason},
    )

    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _map_integrity_error(e)

    db.refresh(pr)

    # Optional reliability hook – ignore if module not yet present.
    return pr


def submit_payment_report(
    db: Session,
    tenant_user_id: UUID,
    request_id: UUID,
    payment_method: str,
    note: Optional[str] = None,
    paid_on: Optional[date] = None,
) -> PaymentRequest:
    """Record a tenant's claimed payment for landlord review."""
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=404, detail="Payment request not found")
    tenancy = db.get(Tenancy, pr.tenancy_id)
    if tenancy is None or str(tenancy.tenant_id) != str(tenant_user_id):
        raise HTTPException(status_code=403, detail="Not your payment request")
    if pr.status != "pending":
        raise HTTPException(status_code=409, detail="This payment request is not awaiting payment")
    report_date = paid_on or date.today()
    if report_date > date.today():
        raise HTTPException(status_code=422, detail="Payment date cannot be in the future")

    pr.status = "submitted"
    pr.payment_method = payment_method
    pr.note = note
    pr.paid_on = report_date
    log_action(
        db,
        action="payment_request.reported",
        actor_id=str(tenant_user_id),
        actor_role="tenant",
        entity_type="payment_request",
        entity_id=str(pr.id),
        metadata={"payment_method": payment_method, "paid_on": report_date.isoformat()},
    )
    db.commit()
    db.refresh(pr)
    return pr


def confirm_payment_receipt(
    db: Session,
    landlord_user_id: UUID,
    request_id: UUID,
) -> PaymentRequest:
    """Confirm a tenant-reported payment and record it in the immutable ledger."""
    pr = db.get(PaymentRequest, request_id)
    if pr is None:
        raise HTTPException(status_code=404, detail="Payment request not found")
    tenancy = db.get(Tenancy, pr.tenancy_id)
    if tenancy is None or str(tenancy.landlord_id) != str(landlord_user_id):
        raise HTTPException(status_code=403, detail="Not your tenancy")
    if pr.status != "submitted":
        raise HTTPException(status_code=409, detail="No tenant payment report is awaiting confirmation")

    pr.status = "accepted"
    pr.decided_by = landlord_user_id
    pr.decided_at = datetime.now(timezone.utc)
    db.add(
        LedgerEntry(
            tenancy_id=pr.tenancy_id,
            entry_type="payment",
            amount=pr.amount,
            payment_request_id=pr.id,
            period_month=pr.period_month,
            paid_on=pr.paid_on,
            created_by=landlord_user_id,
        )
    )
    log_action(
        db,
        action="payment_request.confirmed",
        actor_id=str(landlord_user_id),
        actor_role="landlord",
        entity_type="payment_request",
        entity_id=str(pr.id),
        metadata={"paid_on": pr.paid_on.isoformat()},
    )
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _map_integrity_error(e)
    db.refresh(pr)

    return pr


def get_payment_requests(
    db: Session,
    user_id: UUID,
    role: str,
    tenancy_id: Optional[UUID] = None,
) -> List[PaymentRequest]:
    """Return payment requests visible to the caller.

    - Landlords see requests they created.
    - Tenants see requests for their tenancies.
    - If tenancy_id is provided, filter to that tenancy.
    """
    stmt = select(PaymentRequest)
    if role == "landlord":
        stmt = stmt.where(PaymentRequest.requested_by == user_id)
    elif role == "tenant":
        stmt = stmt.join(Tenancy, PaymentRequest.tenancy_id == Tenancy.id).where(
            Tenancy.tenant_id == user_id
        )

    if tenancy_id:
        stmt = stmt.where(PaymentRequest.tenancy_id == tenancy_id)

    return list(db.scalars(stmt).all())


# ---------------------------------------------------------------------------
# Corrections
# ---------------------------------------------------------------------------

def create_correction(
    db: Session,
    user_id: UUID,
    role: str,
    payload: CorrectionCreate,
) -> LedgerEntry:
    """Insert a correction ledger entry (append-only)."""
    entry = LedgerEntry(
        tenancy_id=payload.tenancy_id,
        entry_type="correction",
        amount=payload.amount,
        corrects_entry_id=payload.corrects_entry_id,
        correction_reason=payload.correction_reason,
        period_month=payload.period_month,
        paid_on=payload.paid_on or date.today(),
        created_by=user_id,
    )
    db.add(entry)
    db.flush()
    log_action(
        db,
        action="ledger.correction.create",
        actor_id=str(user_id),
        actor_role=role,
        entity_type="ledger_entry",
        entity_id=str(entry.id),
        metadata={
            "amount": str(payload.amount),
            "correction_reason": payload.correction_reason,
        },
    )
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise _map_integrity_error(e)

    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------

def get_ledger(
    db: Session,
    user_id: UUID,
    role: str,
    tenancy_id: Optional[UUID] = None,
) -> LedgerWithBalance:
    """Return all ledger entries for a tenancy with a running balance."""
    stmt = select(LedgerEntry).order_by(LedgerEntry.created_at)
    if role == "tenant":
        stmt = stmt.join(Tenancy, LedgerEntry.tenancy_id == Tenancy.id).where(
            Tenancy.tenant_id == user_id
        )
    elif role == "landlord":
        stmt = stmt.join(Tenancy, LedgerEntry.tenancy_id == Tenancy.id).where(
            Tenancy.landlord_id == user_id
        )
    if tenancy_id:
        stmt = stmt.where(LedgerEntry.tenancy_id == tenancy_id)

    entries = list(db.scalars(stmt).all())

    running_balance = Decimal("0.00")
    for e in entries:
        running_balance += Decimal(str(e.amount))

    return LedgerWithBalance(
        entries=[LedgerEntryResponse.model_validate(e) for e in entries],
        running_balance=running_balance,
    )
