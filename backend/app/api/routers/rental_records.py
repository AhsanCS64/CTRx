"""Lease acknowledgements, rent statements and rental dispute cases."""

from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from datetime import date
from html import escape
from io import BytesIO
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.official_profiles import OfficialProfile
from app.db.models.users import User

router = APIRouter(prefix="/records", tags=["rental records"])


def _rows(db, sql, **params):
    return [dict(row) for row in db.execute(text(sql), params).mappings()]


def _one(db, sql, **params):
    row = db.execute(text(sql), params).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Record not found")
    return row


def _audit(db, user, action, kind, record_id):
    log_action(db, action, user.id, user.role, kind, record_id)


def _tenancy(db, user, tenancy_id):
    return _one(db, """
        SELECT t.id, t.tenant_id, t.landlord_id, p.address_line, t.start_date,
               t.monthly_rent, t.deposit, t.rent_due_day, t.status,
               tp.full_name AS tenant_name, lp.full_name AS landlord_name
        FROM tenancies t JOIN properties p ON p.id = t.property_id
        JOIN tenant_profiles tp ON tp.user_id = t.tenant_id
        JOIN landlord_profiles lp ON lp.user_id = t.landlord_id
        WHERE t.id = :id AND :user IN (t.tenant_id, t.landlord_id)
    """, id=tenancy_id, user=user.id)


def _pdf(title, intro, headings, rows, filename):
    output = BytesIO()
    styles = getSampleStyleSheet()
    story = [Paragraph("CTRx", styles["Heading3"]), Paragraph(title, styles["Title"])]
    story.extend(Paragraph(escape(str(line)), styles["BodyText"]) for line in intro)
    story.append(Spacer(1, 18))
    cells = [[Paragraph(escape(str(value)), styles["BodyText"]) for value in row]
             for row in [headings, *rows]]
    table = Table(cells, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dceee9")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7f5")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    SimpleDocTemplate(output, pagesize=A4, leftMargin=44, rightMargin=44).build(story)
    return {"filename": filename, "content_base64": b64encode(output.getvalue()).decode("ascii")}


@router.get("/tenancies")
def tenancies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _rows(db, """
        SELECT t.id, p.address_line, t.status, t.start_date, l.created_at AS lease_created_at
        FROM tenancies t JOIN properties p ON p.id = t.property_id
        LEFT JOIN lease_agreements l ON l.tenancy_id = t.id
        WHERE :user IN (t.tenant_id, t.landlord_id) ORDER BY t.start_date DESC
    """, user=user.id)


@router.get("/leases/{tenancy_id}")
def lease(tenancy_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _tenancy(db, user, tenancy_id)
    return db.execute(text("SELECT * FROM lease_agreements WHERE tenancy_id = :id"),
                      {"id": tenancy_id}).mappings().one_or_none()


@router.post("/leases/{tenancy_id}")
def prepare_lease(tenancy_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _tenancy(db, user, tenancy_id)
    result = db.execute(text("""
        INSERT INTO lease_agreements (tenancy_id, terms)
        SELECT t.id, jsonb_build_object('property', p.address_line, 'tenant', tp.full_name,
            'landlord', lp.full_name, 'start_date', t.start_date, 'monthly_rent', t.monthly_rent,
            'deposit', t.deposit, 'rent_due_day', t.rent_due_day)
        FROM tenancies t JOIN properties p ON p.id = t.property_id
        JOIN tenant_profiles tp ON tp.user_id = t.tenant_id
        JOIN landlord_profiles lp ON lp.user_id = t.landlord_id
        WHERE t.id = :id
        ON CONFLICT (tenancy_id) DO NOTHING
    """), {"id": tenancy_id})
    if result.rowcount:
        _audit(db, user, "lease.prepare", "tenancy", tenancy_id)
    db.commit()
    return lease(tenancy_id, db, user)


@router.post("/leases/{tenancy_id}/acknowledge")
def acknowledge(tenancy_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    record = _tenancy(db, user, tenancy_id)
    field = "tenant_acknowledged_at" if record["tenant_id"] == user.id else "landlord_acknowledged_at"
    existing = _one(db, "SELECT * FROM lease_agreements WHERE tenancy_id = :id FOR UPDATE", id=tenancy_id)
    if not existing[field]:
        db.execute(text(f"UPDATE lease_agreements SET {field} = now() WHERE tenancy_id = :id"), {"id": tenancy_id})
        _audit(db, user, "lease.acknowledge", "tenancy", tenancy_id)
    db.commit()
    return lease(tenancy_id, db, user)


@router.get("/leases/{tenancy_id}/pdf")
def lease_pdf(tenancy_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    agreement = lease(tenancy_id, db, user)
    if agreement is None:
        raise HTTPException(404, "Prepare the lease first")
    tenant_ack = agreement["tenant_acknowledged_at"]
    landlord_ack = agreement["landlord_acknowledged_at"]
    return _pdf("Lease agreement", [
        "Acknowledged by both parties" if tenant_ack and landlord_ack else "Draft awaiting acknowledgement",
        f"Tenant acknowledged: {tenant_ack or 'Pending'}", f"Landlord acknowledged: {landlord_ack or 'Pending'}",
    ], ["Term", "Recorded value"], [
        [key.replace("_", " ").title(), value] for key, value in agreement["terms"].items()
    ], f"lease-{tenancy_id}.pdf")


@router.get("/statements/{tenancy_id}")
def statement(tenancy_id: UUID, start: date, end: date, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenancy = _tenancy(db, user, tenancy_id)
    if start > end:
        raise HTTPException(400, "The end date must be on or after the start date")
    params = {"id": tenancy_id, "start": start.replace(day=1), "end": end.replace(day=1)}
    entries = _rows(db, """
        SELECT id, period_month, paid_on, entry_type, amount, reason, payment_request_id FROM ledger_entries
        WHERE tenancy_id = :id AND period_month BETWEEN :start AND :end
        ORDER BY period_month, created_at, id
    """, **params)
    invoices = _rows(db, """
        SELECT id, period_month, amount, status FROM payment_requests
        WHERE tenancy_id = :id AND period_month BETWEEN :start AND :end
          AND status IN ('pending', 'submitted')
        ORDER BY period_month, id
    """, **params)
    return {"address": tenancy["address_line"], "ledger": entries, "invoices": invoices,
            "posted_total": sum((row["amount"] for row in entries), 0),
            "outstanding_total": sum((row["amount"] for row in invoices), 0)}


@router.get("/statements/{tenancy_id}/pdf")
def statement_pdf(tenancy_id: UUID, start: date, end: date, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = statement(tenancy_id, start, end, db, user)
    rows = [[row["period_month"], row["entry_type"], row["amount"], row["reason"] or row["paid_on"]]
            for row in data["ledger"]]
    rows.extend([row["period_month"], "Invoice", row["amount"], row["status"]] for row in data["invoices"])
    return _pdf("Rent statement", [data["address"], f"Rent periods: {start:%Y-%m} to {end:%Y-%m}",
                f"Posted total: BDT {data['posted_total']}", f"Outstanding: BDT {data['outstanding_total']}"],
                ["Rent period", "Record", "Amount (BDT)", "Details"], rows, f"rent-statement-{start:%Y-%m}.pdf")


class CaseCreate(BaseModel):
    entity_type: Literal["tenancy", "payment_request"]
    entity_id: UUID
    reason: str = Field(min_length=1, max_length=4000)


class CaseMessage(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    status: Literal["under_review", "resolved", "rejected"] | None = None
    content_base64: str | None = Field(default=None, max_length=2_800_000)


CASE_SCOPE = """
    FROM disputes d LEFT JOIN payment_requests pr ON d.entity_type = 'payment_request' AND pr.id = d.entity_id
    LEFT JOIN tenancies t ON t.id = CASE WHEN d.entity_type = 'tenancy' THEN d.entity_id ELSE pr.tenancy_id END
    WHERE d.entity_type IN ('tenancy', 'payment_request')
      AND (:reviewer OR :user IN (t.tenant_id, t.landlord_id))
"""


def _reviewer(db, user):
    if user.role == "admin":
        return True
    official = db.get(OfficialProfile, user.id) if user.role == "government" else None
    return official is not None and official.level == "central"


@router.get("/cases")
def cases(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _rows(db, "SELECT d.* " + CASE_SCOPE + " ORDER BY d.created_at DESC",
                 reviewer=_reviewer(db, user), user=user.id)


@router.post("/cases", status_code=201)
def create_case(payload: CaseCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenancy_id = payload.entity_id
    if payload.entity_type == "payment_request":
        tenancy_id = _one(db, "SELECT tenancy_id FROM payment_requests WHERE id = :id", id=payload.entity_id)["tenancy_id"]
    tenancy = _tenancy(db, user, tenancy_id)
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(400, "Enter a reason for opening the case")
    case_id = db.execute(text("""
        INSERT INTO disputes (raised_by, entity_type, entity_id, reason)
        VALUES (:user, :kind, :record, :reason) RETURNING id
    """), {"user": user.id, "kind": payload.entity_type, "record": payload.entity_id, "reason": reason}).scalar_one()
    recipient = tenancy["landlord_id"] if tenancy["tenant_id"] == user.id else tenancy["tenant_id"]
    db.execute(text("""
        INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
        VALUES (:user, 'cases', :id, 'A rental dispute was opened')
    """), {"user": recipient, "id": case_id})
    _audit(db, user, "dispute.create", "dispute", case_id)
    db.commit()
    return {"id": case_id}


def _case(db, user, case_id, lock=False):
    return _one(db, "SELECT d.*, t.tenant_id, t.landlord_id " + CASE_SCOPE
                + " AND d.id = :id" + (" FOR UPDATE OF d" if lock else ""),
                reviewer=_reviewer(db, user), user=user.id, id=case_id)


@router.get("/cases/{case_id}")
def case_detail(case_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = dict(_case(db, user, case_id))
    case["can_review"] = _reviewer(db, user)
    case["timeline"] = _rows(db, """
        SELECT e.id, e.kind, e.message, e.filename, e.created_at, u.role
        FROM dispute_timeline e JOIN users u ON u.id = e.actor_id
        WHERE e.dispute_id = :id ORDER BY e.id
    """, id=case_id)
    case["care_evidence"] = _rows(db, """
        SELECT id, kind, content FROM tenancy_care
        WHERE :kind = 'tenancy' AND tenancy_id = :tenancy
          AND (content -> 'case_ids') @> jsonb_build_array(CAST(:case AS text))
        ORDER BY created_at
    """, kind=case["entity_type"], tenancy=case["entity_id"], case=str(case_id))
    return case


@router.post("/cases/{case_id}")
def add_case_message(case_id: UUID, payload: CaseMessage, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    case = _case(db, user, case_id, lock=True)
    message = payload.message.strip()
    if case["status"] in {"resolved", "rejected"}:
        raise HTTPException(409, "This case is closed")
    if not message:
        raise HTTPException(400, "Enter a message")
    attachment = None
    extension = None
    if payload.content_base64:
        try:
            attachment = b64decode(payload.content_base64, validate=True)
        except (ValueError, Base64Error) as exc:
            raise HTTPException(400, "Invalid attachment") from exc
        for signature, suffix in ((b"%PDF-", "pdf"), (b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpg")):
            if attachment.startswith(signature):
                extension = suffix
                break
        if not extension or len(attachment) > 2 * 1024 * 1024:
            raise HTTPException(400, "Attach a PDF, PNG or JPEG no larger than 2 MB")
    if payload.status:
        if not _reviewer(db, user):
            raise HTTPException(403, "Only a reviewer can change case status")
        valid = {"open": {"under_review"}, "under_review": {"resolved", "rejected"}}
        if payload.status not in valid.get(case["status"], set()):
            raise HTTPException(409, "Invalid case transition")
        db.execute(text("""
            UPDATE disputes SET status = CAST(:status AS dispute_status), resolution_note = :note,
                resolved_by = :reviewer, resolved_at = CASE WHEN :final THEN now() ELSE NULL END
            WHERE id = :id
        """), {"id": case_id, "status": payload.status, "note": message if payload.status != "under_review" else None,
               "reviewer": user.id if payload.status != "under_review" else None, "final": payload.status != "under_review"})
    kind = payload.status or "message"
    entry_id = db.execute(text("""
        INSERT INTO dispute_timeline (dispute_id, actor_id, kind, message, filename, attachment)
        VALUES (:case, :user, :kind, :message, :filename, :attachment) RETURNING id
    """), {"case": case_id, "user": user.id, "kind": kind, "message": message,
           "filename": f"evidence.{extension}" if extension else None, "attachment": attachment}).scalar_one()
    for recipient in {case["tenant_id"], case["landlord_id"]} - {user.id, None}:
        db.execute(text("""
            INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
            VALUES (:user, 'cases', :id, 'A rental dispute has an update')
        """), {"user": recipient, "id": case_id})
    _audit(db, user, f"dispute.{kind}", "dispute", case_id)
    db.commit()
    return {"id": entry_id}


@router.get("/cases/{case_id}/evidence/{entry_id}")
def evidence(case_id: UUID, entry_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _case(db, user, case_id)
    row = _one(db, """
        SELECT filename, attachment FROM dispute_timeline
        WHERE id = :entry AND dispute_id = :case AND attachment IS NOT NULL
    """, entry=entry_id, case=case_id)
    return {"filename": row["filename"], "content_base64": b64encode(row["attachment"]).decode("ascii")}

