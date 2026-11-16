"""User support tickets and staff responses."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.users import User

router = APIRouter(prefix="/support", tags=["support"])


class TicketCreate(BaseModel):
    category: str = Field(min_length=2, max_length=40)
    subject: str = Field(min_length=4, max_length=160)
    description: str = Field(min_length=10, max_length=4000)
    related_entity_type: str | None = Field(default=None, max_length=40)
    related_entity_id: UUID | None = None


class MessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class TicketUpdate(BaseModel):
    status: str
    priority: str | None = None
    assigned_to: UUID | None = None


def _staff(user):
    return user.role in {"admin", "government"}


@router.get("/tickets")
def list_tickets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.execute(text("""
        SELECT id, ticket_number, created_by, assigned_to, category, subject, description,
               priority, status, related_entity_type, related_entity_id, resolution_note, created_at, updated_at
        FROM support_tickets
        WHERE (:staff AND NOT EXISTS (
            SELECT 1 FROM support_ticket_messages m WHERE m.ticket_id = support_tickets.id
            AND m.is_internal AND :role <> 'admin'
        )) OR created_by = :user
        ORDER BY updated_at DESC
    """), {"staff": _staff(user), "role": user.role, "user": user.id}).mappings()
    return [dict(row) for row in rows]


@router.post("/tickets", status_code=201)
def create_ticket(payload: TicketCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    subject, description = payload.subject.strip(), payload.description.strip()
    if not subject or not description:
        raise HTTPException(400, "Subject and description are required")
    row = db.execute(text("""
        INSERT INTO support_tickets (created_by, category, subject, description, priority, status,
                                     related_entity_type, related_entity_id)
        VALUES (:user, :category, :subject, :description, 'normal', 'open',
                :entity_type, :entity_id)
        RETURNING id, ticket_number
    """), {"user": user.id, "category": payload.category, "subject": subject,
           "description": description, "entity_type": payload.related_entity_type,
           "entity_id": payload.related_entity_id}).mappings().one()
    db.execute(text("""
        INSERT INTO support_ticket_messages (ticket_id, sender_id, message)
        VALUES (:ticket, :user, :message)
    """), {"ticket": row["id"], "user": user.id, "message": description})
    log_action(db, "support.ticket.create", user.id, user.role, "support_ticket", row["id"])
    db.commit()
    return dict(row)


def _ticket(db, user, ticket_id):
    query = "SELECT * FROM support_tickets WHERE id=:id"
    params = {"id": ticket_id}
    if not _staff(user):
        query += " AND created_by=:user"
        params["user"] = user.id
    row = db.execute(text(query), params).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Ticket not found")
    return row


@router.get("/tickets/{ticket_id}")
def ticket_detail(ticket_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _ticket(db, user, ticket_id)
    return db.execute(text("""
        SELECT m.id, m.sender_id, u.role AS sender_role, m.message, m.is_internal, m.created_at
        FROM support_ticket_messages m JOIN users u ON u.id=m.sender_id
        WHERE m.ticket_id=:ticket AND (:admin OR NOT m.is_internal)
        ORDER BY m.created_at
    """), {"ticket": ticket_id, "admin": user.role == "admin"}).mappings().all()


@router.post("/tickets/{ticket_id}/messages", status_code=201)
def add_message(ticket_id: UUID, payload: MessageCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = _ticket(db, user, ticket_id)
    if row["status"] in {"resolved", "closed"}:
        raise HTTPException(409, "This ticket is closed")
    message = payload.message.strip()
    if not message:
        raise HTTPException(400, "Message cannot be blank")
    result = db.execute(text("""
        INSERT INTO support_ticket_messages (ticket_id, sender_id, message)
        VALUES (:ticket, :user, :message) RETURNING id
    """), {"ticket": ticket_id, "user": user.id, "message": message}).scalar_one()
    db.execute(text("""
        UPDATE support_tickets SET status=:status, updated_at=now() WHERE id=:ticket
    """), {"ticket": ticket_id, "status": "in_progress" if _staff(user) else "open"})
    log_action(db, "support.ticket.message", user.id, user.role, "support_ticket", ticket_id)
    db.commit()
    return {"id": result}


@router.patch("/tickets/{ticket_id}")
def update_ticket(ticket_id: UUID, payload: TicketUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not _staff(user):
        raise HTTPException(403, "Staff access required")
    _ticket(db, user, ticket_id)
    if payload.status not in {"open", "in_progress", "waiting_user", "resolved", "closed"}:
        raise HTTPException(400, "Invalid ticket status")
    db.execute(text("""
        UPDATE support_tickets SET status=:status, priority=COALESCE(:priority, priority),
            assigned_to=COALESCE(:assigned, assigned_to), updated_at=now() WHERE id=:id
    """), {"id": ticket_id, "status": payload.status, "priority": payload.priority,
           "assigned": payload.assigned_to})
    log_action(db, "support.ticket.update", user.id, user.role, "support_ticket", ticket_id)
    db.commit()
    return {"id": ticket_id, "status": payload.status}
