"""Tenancy lifecycle endpoints.

Ending a tenancy preserves the original row and changes only its lifecycle
status. A later move is represented by a new tenancy record.
"""

from datetime import date, datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.landlord_profiles import LandlordProfile
from app.db.models.tenant_profiles import TenantProfile
from app.db.models.properties import Property
from app.db.models.property_units import PropertyUnit
from app.db.models.tenancies import Tenancy
from app.db.models.users import User
from app.schemas.tenancies import TenancyResponse, TenancyUpdateStatusRequest

router = APIRouter(prefix="/tenancies", tags=["tenancies"])


@router.get("/mine", response_model=list[TenancyResponse])
def list_my_tenancies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    rows = db.execute(
        select(Tenancy, Property, TenantProfile.full_name, LandlordProfile.full_name, PropertyUnit.unit_number)
        .join(Property, Tenancy.property_id == Property.id)
        .outerjoin(PropertyUnit, PropertyUnit.id == Tenancy.unit_id)
        .outerjoin(TenantProfile, TenantProfile.user_id == Tenancy.tenant_id)
        .outerjoin(LandlordProfile, LandlordProfile.user_id == Tenancy.landlord_id)
        .where(Tenancy.tenant_id == user.id)
        .order_by(Tenancy.start_date.desc())
    ).all()
    return [
        TenancyResponse.model_validate(tenancy).model_copy(update={
            "tenant_name": tenant_name,
            "landlord_name": landlord_name,
            "property_address": property_record.address_line,
            "unit_number": unit_number,
            "property_type": property_record.property_type,
        })
        for tenancy, property_record, tenant_name, landlord_name, unit_number in rows
    ]


@router.post("/{tenancy_id}/status", response_model=TenancyResponse)
def update_my_tenancy_status(
    tenancy_id: str,
    payload: TenancyUpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    tenancy = db.execute(
        select(Tenancy).where(Tenancy.id == tenancy_id, Tenancy.tenant_id == user.id).with_for_update()
    ).scalar_one_or_none()
    if not tenancy:
        raise HTTPException(status_code=404, detail="Tenancy record not found")
    if tenancy.status != "active":
        raise HTTPException(status_code=409, detail="Only an active tenancy can be ended")
    end_date = payload.end_date or date.today()
    if end_date <= tenancy.start_date:
        raise HTTPException(status_code=400, detail="The end date must be after the tenancy start date")
    tenancy.status = payload.status
    tenancy.end_date = end_date
    db.commit()
    db.refresh(tenancy)
    return tenancy



class TenancyStartUpdate(BaseModel):
    start_date: date


@router.patch("/{tenancy_id}/start-date")
def correct_start_date(
    tenancy_id: UUID,
    payload: TenancyStartUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "landlord":
        raise HTTPException(403, "Only the tenancy landlord can correct the start date")
    tenancy = db.execute(
        select(Tenancy)
        .where(Tenancy.id == tenancy_id, Tenancy.landlord_id == user.id)
        .with_for_update()
    ).scalar_one_or_none()
    if tenancy is None:
        raise HTTPException(404, "Tenancy not found")

    start = payload.start_date
    if start == tenancy.start_date:
        return {"start_date": start}
    if tenancy.end_date and start >= tenancy.end_date:
        raise HTTPException(422, "The start date must be before the tenancy end date")

    params = {"tenancy": tenancy.id, "start": start, "month": start.replace(day=1)}
    lease = db.execute(text("""
        SELECT terms, tenant_acknowledged_at, landlord_acknowledged_at
        FROM lease_agreements WHERE tenancy_id = :tenancy FOR UPDATE
    """), params).one_or_none()
    conflicts = _start_date_conflicts(db, params)
    if conflicts:
        raise HTTPException(409, "The new start date would exclude existing rent or feedback records.")

    if lease and (lease.tenant_acknowledged_at or lease.landlord_acknowledged_at):
        log_action(db, "tenancy.start_date.proposed", user.id, user.role, "tenancy", tenancy.id,
                   metadata={"start_date": start.isoformat(), "previous_start_date": tenancy.start_date.isoformat()})
        _notify_start_date(db, tenancy.tenant_id, tenancy.id,
                           f"Your landlord proposed a tenancy start date of {start:%d %B %Y}. Review it in Lease agreements.")
        db.commit()
        return {"start_date": tenancy.start_date, "proposed_start_date": start}

    return _apply_start_date(db, tenancy, start, user)


def _start_date_conflicts(db: Session, params):
    return db.execute(text("""
        SELECT EXISTS (
            SELECT 1 FROM payment_requests WHERE tenancy_id = :tenancy AND period_month < :month
            UNION ALL
            SELECT 1 FROM ledger_entries
            WHERE tenancy_id = :tenancy AND (period_month < :month OR paid_on < :start)
            UNION ALL
            SELECT 1 FROM monthly_tenancy_feedback WHERE tenancy_id = :tenancy AND period_month < :month
            UNION ALL
            SELECT 1 FROM reliability_score_events WHERE tenancy_id = :tenancy AND period_month < :month
        )
    """), params).scalar_one()


def _notify_start_date(db: Session, recipient: UUID, tenancy_id: UUID, message: str):
    db.execute(text("""
        INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
        VALUES (:recipient, 'leases', :tenancy, :message)
    """), {"recipient": recipient, "tenancy": tenancy_id, "message": message})


def _apply_start_date(db: Session, tenancy: Tenancy, start: date, user: User, previous_lease=None):
    params = {"tenancy": tenancy.id, "start": start}
    old_start = tenancy.start_date
    tenancy.start_date = start
    try:
        db.flush()
        db.execute(text("""
            UPDATE lease_agreements
            SET terms = jsonb_set(terms, '{start_date}', to_jsonb(CAST(:start AS date)))
            WHERE tenancy_id = :tenancy
        """), params)
        details = {"previous_start_date": old_start.isoformat(), "start_date": start.isoformat()}
        if previous_lease:
            details["previous_terms"] = previous_lease.terms
            details["previous_tenant_acknowledged_at"] = str(previous_lease.tenant_acknowledged_at or "")
            details["previous_landlord_acknowledged_at"] = str(previous_lease.landlord_acknowledged_at or "")
            db.execute(text("""
                UPDATE lease_agreements SET tenant_acknowledged_at = now(), landlord_acknowledged_at = now()
                WHERE tenancy_id = :tenancy
            """), params)
        _notify_start_date(db, tenancy.landlord_id if previous_lease else tenancy.tenant_id, tenancy.id,
                           f"The tenancy start date was corrected from {old_start:%d %B %Y} to {start:%d %B %Y}.")
        log_action(db, "tenancy.start_date.correct", user.id, user.role, "tenancy", tenancy.id, metadata=details)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23P01":
            raise HTTPException(409, "These dates overlap another active tenancy for this property.") from exc
        raise
    return {"start_date": start}


def _pending_start_date(db: Session, tenancy_id: UUID):
    row = db.execute(text("""
        SELECT id, action, metadata FROM audit_logs
        WHERE entity_type = 'tenancy' AND entity_id = :tenancy
          AND action IN ('tenancy.start_date.proposed', 'tenancy.start_date.correct', 'tenancy.start_date.declined')
        ORDER BY id DESC LIMIT 1
    """), {"tenancy": tenancy_id}).one_or_none()
    if row and row.action == "tenancy.start_date.proposed":
        return {"id": row.id, **row.metadata}
    return None


@router.get("/{tenancy_id}/start-date/proposal")
def start_date_proposal(tenancy_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenancy = db.get(Tenancy, tenancy_id)
    if not tenancy or user.id not in (tenancy.tenant_id, tenancy.landlord_id):
        raise HTTPException(404, "Tenancy not found")
    return _pending_start_date(db, tenancy_id)


class StartDateDecision(BaseModel):
    proposal_id: int
    decision: Literal["approve", "decline"]


@router.post("/{tenancy_id}/start-date/proposal")
def decide_start_date(
    tenancy_id: UUID, payload: StartDateDecision,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    if user.role != "tenant":
        raise HTTPException(403, "Only the tenant can respond to a proposed start date")
    tenancy = db.execute(
        select(Tenancy).where(Tenancy.id == tenancy_id, Tenancy.tenant_id == user.id).with_for_update()
    ).scalar_one_or_none()
    if not tenancy:
        raise HTTPException(404, "Tenancy not found")
    proposal = _pending_start_date(db, tenancy_id)
    if not proposal or proposal["id"] != payload.proposal_id:
        raise HTTPException(409, "This proposal changed. Refresh the lease and try again.")
    if payload.decision == "decline":
        log_action(db, "tenancy.start_date.declined", user.id, user.role, "tenancy", tenancy_id,
                   metadata={"proposal_id": payload.proposal_id})
        _notify_start_date(db, tenancy.landlord_id, tenancy.id, "Your tenant declined the proposed start-date correction.")
        db.commit()
        return {"start_date": tenancy.start_date}
    start = date.fromisoformat(proposal["start_date"])
    if tenancy.start_date.isoformat() != proposal["previous_start_date"] or (tenancy.end_date and start >= tenancy.end_date):
        raise HTTPException(409, "The tenancy dates changed. Ask the landlord to submit a new proposal.")
    params = {"tenancy": tenancy_id, "start": start, "month": start.replace(day=1)}
    if _start_date_conflicts(db, params):
        raise HTTPException(409, "The new start date would exclude existing rent or feedback records.")
    lease = db.execute(text("""
        SELECT terms, tenant_acknowledged_at, landlord_acknowledged_at
        FROM lease_agreements WHERE tenancy_id = :tenancy FOR UPDATE
    """), params).one_or_none()
    if not lease:
        raise HTTPException(409, "The lease is unavailable.")
    return _apply_start_date(db, tenancy, start, user, previous_lease=lease)


FeedbackCategory = Literal["communication", "rent_handling", "property_care", "repairs", "conduct"]


class FeedbackInput(BaseModel):
    period_month: date | None = None
    rating: Literal["positive", "satisfactory", "concern"]
    remark: str = Field(min_length=1, max_length=1500)


@router.get("/feedback")
def tenancy_feedback(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role not in ("tenant", "landlord"):
        raise HTTPException(403, "Tenant or landlord role required")
    rows = db.execute(text("""
        SELECT t.id, t.start_date, t.end_date, p.address_line, u.unit_number, t.status,
               CASE WHEN t.tenant_id = :user THEN lp.full_name ELSE tp.full_name END AS counterpart_name,
               COALESCE(json_agg(json_build_object(
                   'category', f.category, 'rating', f.rating, 'remark', f.remark, 'period_month', f.period_month,
                   'updated_at', f.updated_at, 'mine', f.author_id = :user
               ) ORDER BY f.updated_at DESC) FILTER (WHERE f.author_id IS NOT NULL), '[]') AS feedback
        FROM tenancies t JOIN properties p ON p.id = t.property_id
        LEFT JOIN property_units u ON u.id = t.unit_id
        LEFT JOIN tenant_profiles tp ON tp.user_id = t.tenant_id
        LEFT JOIN landlord_profiles lp ON lp.user_id = t.landlord_id
        LEFT JOIN (
            SELECT tenancy_id, author_id, category, rating, remark, updated_at, NULL::date AS period_month
            FROM tenancy_feedback
            UNION ALL
            SELECT tenancy_id, author_id, category, rating, remark, updated_at, period_month
            FROM monthly_tenancy_feedback
        ) f ON f.tenancy_id = t.id
             AND f.author_id IN (t.tenant_id, t.landlord_id)
        WHERE :user IN (t.tenant_id, t.landlord_id)
        GROUP BY t.id, p.address_line, u.unit_number, lp.full_name, tp.full_name
        ORDER BY t.start_date DESC, t.id
    """), {"user": user.id}).mappings()
    return [dict(row) for row in rows]


@router.put("/{tenancy_id}/feedback/{category}")
def save_feedback(
    tenancy_id: UUID,
    category: FeedbackCategory,
    payload: FeedbackInput,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role not in ("tenant", "landlord"):
        raise HTTPException(403, "Tenant or landlord role required")
    tenancy = db.get(Tenancy, tenancy_id)
    if tenancy is None or user.id not in (tenancy.tenant_id, tenancy.landlord_id):
        raise HTTPException(404, "Tenancy not found")
    remark = payload.remark.strip()
    if not remark:
        raise HTTPException(422, "A remark is required")
    today = datetime.now(timezone(timedelta(hours=6))).date()
    period = payload.period_month or min(today, tenancy.end_date or today).replace(day=1)
    if (
        period.day != 1 or period > today or tenancy.start_date > today
        or period < tenancy.start_date.replace(day=1)
        or (tenancy.end_date and period > tenancy.end_date.replace(day=1))
    ):
        raise HTTPException(422, "Choose a current or past month within the tenancy")
    db.execute(text("""
        INSERT INTO monthly_tenancy_feedback (tenancy_id, author_id, period_month, category, rating, remark)
        VALUES (:tenancy, :author, :period, :category, :rating, :remark)
        ON CONFLICT (tenancy_id, author_id, period_month, category) DO UPDATE
        SET rating = EXCLUDED.rating, remark = EXCLUDED.remark, updated_at = now()
    """), {"tenancy": tenancy.id, "author": user.id, "period": period, "category": category,
           "rating": payload.rating, "remark": remark})
    log_action(db, "tenancy.feedback.save", user.id, user.role, "tenancy", tenancy.id,
               metadata={"category": category, "rating": payload.rating, "period_month": period.isoformat()})
    db.commit()
    return {"saved": True}
