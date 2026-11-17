"""Notification inbox, tenant sharing controls and reliability history."""

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.users import User
from app.services.scoring import reliability_history

router = APIRouter(prefix="/workspace", tags=["workspace"])

_CONSENT_SCOPE_MAP = {
    "tenancies": ("tenancy_history",),
    "reliability": ("reliability_score", "payment_history"),
    "certificates": ("ric_certificate",),
}


def _consent_scopes(categories: list[str]) -> list[str]:
    return list(dict.fromkeys(scope for category in categories for scope in _CONSENT_SCOPE_MAP[category]))


class SharingRequest(BaseModel):
    landlord_id: UUID
    categories: list[Literal["tenancies", "reliability", "certificates"]] = Field(min_length=1, max_length=3)
    expires_at: AwareDatetime


class SharingUpdate(BaseModel):
    categories: list[Literal["tenancies", "reliability", "certificates"]] = Field(min_length=1, max_length=3)


@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.execute(text("""
        SELECT id, destination, record_id, message, created_at, read_at
        FROM workspace_notifications WHERE recipient_id = :user
        ORDER BY (read_at IS NULL) DESC, id DESC LIMIT 100
    """), {"user": user.id}).mappings().all()
    unread = db.execute(text("""
        SELECT count(*) FROM workspace_notifications WHERE recipient_id = :user AND read_at IS NULL
    """), {"user": user.id}).scalar_one()
    return {"items": [dict(row) for row in items], "unread": unread}


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.execute(text("""
        UPDATE workspace_notifications SET read_at = COALESCE(read_at, now())
        WHERE id = :id AND recipient_id = :user RETURNING id
    """), {"id": notification_id, "user": user.id}).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Notification not found")
    db.commit()
    return {"id": row}


@router.get("/reliability")
def reliability(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(403, "Tenant role required")
    return reliability_history(db, user.id)


@router.get("/sharing")
def sharing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [dict(row) for row in db.execute(text("""
        SELECT g.*, u.email AS other_email FROM rental_history_grants g
        JOIN users u ON u.id = CASE WHEN g.tenant_id = :user THEN g.landlord_id ELSE g.tenant_id END
        WHERE g.tenant_id = :user OR
            (g.landlord_id = :user AND g.revoked_at IS NULL AND g.expires_at > now())
        ORDER BY g.id DESC
    """), {"user": user.id}).mappings()]


@router.post("/sharing")
def grant_sharing(payload: SharingRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(403, "Tenant role required")
    if payload.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(400, "Choose a future expiration time")
    if not db.execute(text("SELECT 1 FROM users WHERE id = :id AND role = 'landlord' AND is_active"),
                      {"id": payload.landlord_id}).scalar_one_or_none():
        raise HTTPException(404, "Landlord not found")
    grant_id = db.execute(text("""
        INSERT INTO rental_history_grants (tenant_id, landlord_id, categories, expires_at)
        VALUES (:tenant, :landlord, :categories, :expires) RETURNING id
    """), {"tenant": user.id, "landlord": payload.landlord_id,
           "categories": list(dict.fromkeys(payload.categories)), "expires": payload.expires_at}).scalar_one()
    log_action(db, "sharing.grant", user.id, user.role, "user", payload.landlord_id,
               metadata={"grant_id": grant_id})
    db.execute(text("""
        INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
        VALUES (:landlord, 'sharing', :tenant, 'A tenant shared rental history with you')
    """), {"landlord": payload.landlord_id, "tenant": user.id})
    db.execute(text("""
        INSERT INTO consent_events (tenant_id, landlord_id, event_type, scopes, actor_id, reason, metadata)
        VALUES (:tenant, :landlord, 'granted', :scopes, :actor, 'Tenant granted rental history access',
                jsonb_build_object('grant_id', :grant))
    """), {"tenant": user.id, "landlord": payload.landlord_id,
           "scopes": _consent_scopes(payload.categories), "actor": user.id, "grant": grant_id})
    db.commit()
    return {"id": grant_id}


@router.delete("/sharing/{grant_id}")
def revoke_sharing(grant_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    row = db.execute(text("""
        UPDATE rental_history_grants SET revoked_at = now()
        WHERE id = :id AND tenant_id = :user AND revoked_at IS NULL RETURNING landlord_id, categories
    """), {"id": grant_id, "user": user.id}).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Active grant not found")
    landlord_id = row["landlord_id"]
    log_action(db, "sharing.revoke", user.id, user.role, "user", landlord_id,
               metadata={"grant_id": grant_id})
    db.execute(text("""
        INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
        VALUES (:landlord, 'sharing', :tenant, 'A tenant revoked access to their rental history')
    """), {"landlord": landlord_id, "tenant": user.id})
    db.execute(text("""
        INSERT INTO consent_events (access_grant_id, tenant_id, landlord_id, event_type, scopes,
                                   actor_id, reason, metadata)
        VALUES (NULL, :tenant, :landlord, 'revoked', :scopes, :actor,
                'Tenant revoked rental history access', jsonb_build_object('grant_id', :grant))
    """), {"tenant": user.id, "landlord": landlord_id, "scopes": _consent_scopes(row["categories"]),
           "actor": user.id, "grant": grant_id})
    db.commit()
    return {"id": grant_id}


@router.put("/sharing/{grant_id}")
def update_sharing(grant_id: int, payload: SharingUpdate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(403, "Tenant role required")
    categories = list(dict.fromkeys(payload.categories))
    grant = db.execute(text("""
        UPDATE rental_history_grants SET categories = :categories
        WHERE id = :id AND tenant_id = :tenant AND revoked_at IS NULL AND expires_at > now()
        RETURNING landlord_id
    """), {"categories": categories, "id": grant_id, "tenant": user.id}).scalar_one_or_none()
    if grant is None:
        raise HTTPException(404, "Active grant not found")
    log_action(db, "sharing.update", user.id, user.role, "user", grant,
               metadata={"grant_id": grant_id, "categories": categories})
    db.execute(text("""
        INSERT INTO consent_events (tenant_id, landlord_id, event_type, scopes, actor_id, reason, metadata)
        VALUES (:tenant, :landlord, 'granted', :scopes, :actor,
                'Tenant updated shared rental history permissions', jsonb_build_object('grant_id', :grant))
    """), {"tenant": user.id, "landlord": grant, "scopes": _consent_scopes(categories),
           "actor": user.id, "grant": grant_id})
    db.commit()
    return {"id": grant_id, "categories": categories}


@router.get("/sharing/{grant_id}/history")
def shared_history(grant_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    grant = db.execute(text("""
        SELECT tenant_id, categories FROM rental_history_grants
        WHERE id = :id AND landlord_id = :user AND revoked_at IS NULL AND expires_at > now()
        FOR SHARE
    """), {"id": grant_id, "user": user.id}).mappings().one_or_none()
    if grant is None:
        raise HTTPException(404, "Active grant not found")
    result = {}
    if "tenancies" in grant["categories"]:
        result["tenancies"] = [dict(row) for row in db.execute(text("""
            SELECT start_date, end_date, status FROM tenancies WHERE tenant_id = :tenant
            ORDER BY start_date DESC
        """), {"tenant": grant["tenant_id"]}).mappings()]
    if "reliability" in grant["categories"]:
        result["reliability"] = reliability_history(db, grant["tenant_id"])
    return result


@router.get("/privacy")
def privacy_history(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    grants = db.execute(text("""
        SELECT g.id, g.landlord_id, u.email AS landlord_email, g.categories,
               g.expires_at, g.revoked_at
        FROM rental_history_grants g JOIN users u ON u.id = g.landlord_id
        WHERE g.tenant_id = :user ORDER BY g.id DESC
    """), {"user": user.id}).mappings().all()
    events = db.execute(text("""
        SELECT id, event_type, scopes, reason, created_at
        FROM consent_events WHERE tenant_id = :user ORDER BY created_at DESC LIMIT 100
    """), {"user": user.id}).mappings().all()
    return {"grants": [dict(row) for row in grants], "events": [dict(row) for row in events]}


@router.get("/shared-certificates")
def shared_certificates(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "landlord":
        raise HTTPException(403, "Landlord role required")
    rows = db.execute(text("""
        SELECT DISTINCT c.id, c.ric_number, c.status, c.issued_at,
               a.full_name AS applicant_name, ar.name AS area_name
        FROM rental_history_grants g
        JOIN users tenant ON tenant.id = g.tenant_id
        JOIN ric_applications a ON a.applicant_user_id = tenant.id OR a.email = tenant.email
        JOIN rental_identity_certificates c ON c.application_id = a.id
        JOIN areas ar ON ar.id = a.area_id
        WHERE g.landlord_id = :landlord AND g.revoked_at IS NULL AND g.expires_at > now()
          AND g.categories @> ARRAY['certificates']::text[]
        ORDER BY c.issued_at DESC
    """), {"landlord": user.id}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/reliability/events")
def reliability_events(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(403, "Tenant role required")
    return db.execute(text("""
        SELECT e.id, e.event_type, e.points_delta, e.description, e.created_at,
               e.ledger_entry_id, e.tenancy_id
        FROM reliability_score_events e
        JOIN reliability_scores s ON s.id = e.score_id
        WHERE s.tenant_id = :user ORDER BY e.created_at DESC
    """), {"user": user.id}).mappings().all()


@router.get("/certificates/{certificate_id}/delivery")
def certificate_delivery(certificate_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    certificate = db.execute(text("""
        SELECT c.id FROM rental_identity_certificates c
        JOIN ric_applications a ON a.id = c.application_id
        WHERE c.id = :id AND (
            a.applicant_user_id = :user OR a.email = :email OR :role = 'admin'
            OR :user IN (SELECT user_id FROM official_profiles WHERE level = 'central')
            OR EXISTS (
                SELECT 1 FROM rental_history_grants g JOIN users tenant ON tenant.id = g.tenant_id
                WHERE (g.tenant_id = a.applicant_user_id OR tenant.email = a.email)
                  AND g.landlord_id = :user
                  AND g.revoked_at IS NULL AND g.expires_at > now()
                  AND g.categories @> ARRAY['certificates']::text[]
            )
        )
    """), {"id": certificate_id, "user": user.id, "email": user.email, "role": user.role}).scalar_one_or_none()
    if certificate is None:
        raise HTTPException(404, "Certificate not found")
    return db.execute(text("""
        SELECT id, document_id, event_type, delivery_channel, success, failure_reason, created_at
        FROM certificate_delivery_events WHERE certificate_id = :id ORDER BY created_at DESC
    """), {"id": certificate_id}).mappings().all()
