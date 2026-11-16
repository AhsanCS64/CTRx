from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.properties import Property
from app.db.models.tenancies import Tenancy
from app.db.models.tenancy_care import TenancyCare
from app.db.models.users import User
from app.schemas.tenancy_care import CareCreate, CareUpdate, Deposit, DeductionResponse, LinkDispute, RecordReturn, RepairUpdate

router = APIRouter(prefix="/tenancy-care", tags=["tenancy care"])


def scope(user):
    if user.role == "tenant":
        return Tenancy.tenant_id == user.id
    if user.role == "landlord":
        return Tenancy.landlord_id == user.id
    raise HTTPException(403, "Tenancy access required")


def tenancy_for(db, user, tenancy_id, lock=False):
    query = select(Tenancy).where(Tenancy.id == tenancy_id, scope(user))
    tenancy = db.scalar(query.with_for_update() if lock else query)
    if tenancy is None:
        raise HTTPException(404, "Tenancy not found")
    return tenancy


def serialize(record):
    return {"id": record.id, "kind": record.kind, "created_at": record.created_at, **record.content}


@router.get("")
def tenancies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(
        select(Tenancy, Property.address_line)
        .join(Property, Tenancy.property_id == Property.id)
        .where(scope(user))
        .order_by(Tenancy.start_date.desc())
    )
    return [
        {"id": row.id, "address": address, "status": row.status, "start_date": row.start_date, "deposit": str(row.deposit)}
        for row, address in rows
    ]


@router.get("/{tenancy_id}")
def records(tenancy_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenancy_for(db, user, tenancy_id)
    return [serialize(record) for record in db.scalars(
        select(TenancyCare).where(TenancyCare.tenancy_id == tenancy_id).order_by(TenancyCare.created_at.desc())
    )]


@router.post("/{tenancy_id}", status_code=201)
def create(tenancy_id: UUID, payload: CareCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenancy = tenancy_for(db, user, tenancy_id, lock=True)
    content = payload.model_dump(mode="json", exclude={"kind"})
    if payload.kind == "maintenance":
        if user.role != "tenant" or tenancy.status != "active":
            raise HTTPException(403, "Only the current tenant can report maintenance")
        content.update(status="reported", history=[])
    elif db.scalar(select(TenancyCare.id).where(TenancyCare.tenancy_id == tenancy_id, TenancyCare.kind == payload.kind)):
        raise HTTPException(409, "This tenancy already has that record")

    if isinstance(payload, Deposit):
        if user.role != "landlord" or tenancy.status == "active":
            raise HTTPException(403, "The landlord can record settlement after the tenancy ends")
        deductions = sum(item.amount for item in payload.deductions)
        expected = tenancy.deposit - deductions
        if expected < 0 or payload.returned > expected or (payload.returned > 0 and not payload.returned_on):
            raise HTTPException(422, "Check the deductions, returned amount and return date")
        content.update(original=str(tenancy.deposit), balance=str(expected - payload.returned), responses={}, returns=[])
        if payload.returned:
            content["returns"].append({
                "amount": str(payload.returned), "returned_on": payload.returned_on.isoformat(), "reference": payload.reference,
            })
    if payload.kind in {"move_in", "move_out"}:
        content["acknowledgements"] = {}

    record = TenancyCare(tenancy_id=tenancy_id, kind=payload.kind, content=content)
    db.add(record)
    db.flush()
    result = serialize(record)
    log_action(db, f"tenancy_care.create.{record.kind}", user.id, user.role, "tenancy_care", record.id)
    db.commit()
    return result


@router.post("/{tenancy_id}/{record_id}")
def update(tenancy_id: UUID, record_id: UUID, payload: CareUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    tenancy_for(db, user, tenancy_id)
    record = db.scalar(select(TenancyCare).where(
        TenancyCare.id == record_id, TenancyCare.tenancy_id == tenancy_id
    ).with_for_update())
    if record is None:
        raise HTTPException(404, "Record not found")
    content = dict(record.content)
    now = datetime.now(timezone.utc).isoformat()

    if isinstance(payload, RepairUpdate):
        if record.kind != "maintenance" or user.role != "landlord":
            raise HTTPException(403, "Only the landlord can update repairs")
        allowed = {"reported": {"scheduled"}, "scheduled": {"scheduled", "in_progress", "completed"}, "in_progress": {"completed"}, "completed": set()}
        if payload.status not in allowed[content["status"]] or (payload.status == "scheduled" and not payload.scheduled_for):
            raise HTTPException(409, "Choose a valid repair status and schedule date")
        event = payload.model_dump(mode="json", exclude={"action"})
        content.update(status=payload.status, history=[*content["history"], {**event, "at": now}])
    elif isinstance(payload, DeductionResponse):
        if record.kind != "deposit" or user.role != "tenant":
            raise HTTPException(403, "Only the tenant can respond to deductions")
        if payload.index >= len(content["deductions"]) or (payload.decision == "disputed" and not payload.note.strip()):
            raise HTTPException(422, "Select a deduction and provide a reason if disputing it")
        key = str(payload.index)
        content["responses"] = {**content["responses"], key: {
            "decision": payload.decision, "note": payload.note.strip(), "at": now,
        }}
    elif isinstance(payload, RecordReturn):
        if record.kind != "deposit" or user.role != "landlord":
            raise HTTPException(403, "Only the landlord can record deposit returns")
        balance = Decimal(content["balance"])
        if payload.amount > balance:
            raise HTTPException(422, "The return exceeds the outstanding deposit balance")
        payment = payload.model_dump(mode="json", exclude={"action"})
        content.update(
            balance=str(balance - payload.amount),
            returned=str(Decimal(content["returned"]) + payload.amount),
            returned_on=payment["returned_on"],
            reference=payment["reference"],
            returns=[*content.get("returns", []), payment],
        )
    elif isinstance(payload, LinkDispute):
        if record.kind not in {"move_in", "move_out", "deposit"}:
            raise HTTPException(409, "This record cannot be linked to a dispute")
        case = db.scalar(text("""
            SELECT id FROM disputes WHERE id = :case AND entity_type = 'tenancy' AND entity_id = :tenancy
        """), {"case": payload.case_id, "tenancy": tenancy_id})
        if not case:
            raise HTTPException(404, "Choose a dispute for this tenancy")
        content["case_ids"] = sorted({*content.get("case_ids", []), str(case)})
    else:
        if record.kind not in {"move_in", "move_out"}:
            raise HTTPException(409, "Only inspections can be acknowledged")
        content["acknowledgements"] = {user.role: now, **content["acknowledgements"]}

    record.content = content
    result = serialize(record)
    log_action(db, f"tenancy_care.{payload.action}", user.id, user.role, "tenancy_care", record.id)
    db.commit()
    return result


