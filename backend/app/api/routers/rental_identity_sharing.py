"""Time-limited tenant-authorized public rental identity verification."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.audit import log_action
from app.core.security import _create_token, decode_token
from app.db.models.rental_identity_certificates import RentalIdentityCertificate
from app.db.models.ric_applications import RicApplication
from app.db.models.users import User
from app.services.scoring import reliability_history

router = APIRouter(tags=["rental identity sharing"])
SHARE_DURATION = timedelta(hours=24)


class ShareVerificationRequest(BaseModel):
    token: str = Field(min_length=1, max_length=2048)


def _active_certificate(db: Session, certificate_id: UUID):
    row = db.execute(
        select(RentalIdentityCertificate, RicApplication.email, RicApplication.full_name)
        .join(RicApplication, RicApplication.id == RentalIdentityCertificate.application_id)
        .where(RentalIdentityCertificate.id == certificate_id, RentalIdentityCertificate.status == "active")
    ).one_or_none()
    if row is None or (
        row[0].expires_at is not None and row[0].expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(status_code=404, detail="No active certificate is available for this link")
    return row


@router.post("/certificates/{certificate_id}/share")
def share_certificate(
    certificate_id: UUID,
    response: Response,
    user: User = Depends(require_role(["tenant"])),
    db: Session = Depends(get_db),
):
    certificate, email, _ = _active_certificate(db, certificate_id)
    if email != user.email:
        raise HTTPException(status_code=404, detail="No active certificate is available for this link")

    token = _create_token({"type": "rental_identity_share", "sub": str(certificate.id)}, SHARE_DURATION)
    log_action(db, "share_rental_identity", user.id, user.role, "certificate", certificate.id)
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {"token": token, "expires_in_hours": 24}


@router.post("/public/rental-identity/verify")
def verify_shared_identity(
    payload: ShareVerificationRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    claims = decode_token(payload.token)
    if claims.get("type") != "rental_identity_share":
        raise HTTPException(status_code=404, detail="This is not a rental identity share link")
    certificate, email, applicant_name = _active_certificate(db, UUID(claims["sub"]))
    tenant_id = db.scalar(select(User.id).where(User.email == email, User.role == "tenant", User.is_active.is_(True)))
    if tenant_id is None:
        raise HTTPException(status_code=404, detail="The shared rental identity is unavailable")

    history = reliability_history(db, tenant_id)
    response.headers["Cache-Control"] = "no-store"
    return {
        "applicant_name": applicant_name,
        "ric_number": certificate.ric_number,
        "issued_at": certificate.issued_at,
        "status": certificate.status,
        "recorded_payment_periods": history["confirmed_payment_periods"],
        "reliability_score": history["score"],
    }
