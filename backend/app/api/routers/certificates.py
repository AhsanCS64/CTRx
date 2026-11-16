"""Router for certificate issuance and PDF download.

- ``POST /certificates/issue/{app_id}`` – triggers the A/B issuance flow for an
  approved application. Returns ``CertificateIssueResponse``.
- ``GET /certificates/{cert_id}/pdf`` – returns the stored PDF file as a
  ``application/pdf`` response. If the document is not yet generated, returns a
  202 Accepted indicating the PDF is pending (the background job will retry).
"""

import base64
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.config import settings
from app.db.models.areas import Area
from app.db.models.certificate_documents import CertificateDocument
from app.db.models.official_profiles import OfficialProfile
from app.db.models.rental_identity_certificates import RentalIdentityCertificate
from app.db.models.ric_applications import RicApplication
from app.schemas.certificate import CertificateIssueResponse
from app.services.certificate_issuance import issue_certificate_flow, render_and_register_pdf

router = APIRouter(prefix="/certificates", tags=["certificates"])

# Only government officials (any level) can issue certificates.
require_gov = require_role(["government"])

@router.get("")
def list_certificates(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "government":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Government role required")
    official = db.get(OfficialProfile, current_user.id)
    if official is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Official profile missing")

    stmt = (
        select(RentalIdentityCertificate, RicApplication, Area)
        .join(RicApplication, RicApplication.id == RentalIdentityCertificate.application_id)
        .join(Area, Area.id == RicApplication.area_id)
    )
    if official.level == "local":
        stmt = stmt.where(RicApplication.area_id == official.area_id)
    rows = db.execute(stmt.order_by(RentalIdentityCertificate.issued_at.desc())).all()
    return [
        {
            "id": str(cert.id),
            "ric_number": cert.ric_number,
            "status": cert.status,
            "issued_at": cert.issued_at,
            "expires_at": cert.expires_at,
            "applicant_name": application.full_name,
            "area_name": area.name,
        }
        for cert, application, area in rows
    ]

@router.get("/mine")
def list_my_certificates(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    rows = db.execute(
        select(RentalIdentityCertificate, RicApplication, Area)
        .join(RicApplication, RicApplication.id == RentalIdentityCertificate.application_id)
        .join(Area, Area.id == RicApplication.area_id)
        .where(RicApplication.email == current_user.email)
        .order_by(RentalIdentityCertificate.issued_at.desc())
    ).all()
    return [
        {
            "id": str(cert.id),
            "ric_number": cert.ric_number,
            "status": cert.status,
            "issued_at": cert.issued_at,
            "expires_at": cert.expires_at,
            "applicant_name": application.full_name,
            "area_name": area.name,
        }
        for cert, application, area in rows
    ]

@router.post("/issue/{app_id}", response_model=CertificateIssueResponse)
def issue_certificate(app_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role != "government":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Government role required")
    official = db.get(OfficialProfile, current_user.id)
    if official is None or official.level != "central":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Central official access required",
        )
    result = issue_certificate_flow(db, app_id)
    db.commit()
    return CertificateIssueResponse(**result)

def _authorize_download(db, cert_id, user):
    application = db.scalar(select(RicApplication).join(
        RentalIdentityCertificate, RentalIdentityCertificate.application_id == RicApplication.id
    ).where(RentalIdentityCertificate.id == cert_id))
    if application is not None:
        if user.role == "admin" or (user.role == "tenant" and user.email == application.email):
            return
        if user.role == "government":
            official = db.get(OfficialProfile, user.id)
            if official and (official.level == "central" or official.area_id == application.area_id):
                return
        if user.role == "landlord":
            shared = db.execute(text("""
                SELECT EXISTS (
                    SELECT 1 FROM rental_history_grants g
                    JOIN users tenant ON tenant.id = g.tenant_id
                    WHERE g.landlord_id = :landlord
                      AND tenant.email = :email
                      AND g.revoked_at IS NULL AND g.expires_at > now()
                      AND g.categories @> ARRAY['certificates']::text[]
                )
            """), {"landlord": user.id, "email": application.email}).scalar_one()
            if shared:
                return
    raise HTTPException(404, "Certificate not found")


@router.post("/{cert_id}/regenerate")
def regenerate(cert_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    official = db.get(OfficialProfile, current_user.id) if current_user.role == "government" else None
    if current_user.role != "admin" and not (official and official.level == "central"):
        raise HTTPException(403, "Central official or administrator access required")
    _authorize_download(db, cert_id, current_user)
    return {"updated": render_and_register_pdf(db, cert_id, actor=current_user, upgrade=True)}


@router.api_route("/{cert_id}/pdf", methods=["GET", "POST"])
def download_pdf(cert_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    _authorize_download(db, cert_id, current_user)
    doc = db.query(CertificateDocument).filter(CertificateDocument.certificate_id == cert_id, CertificateDocument.is_current == True).first()
    if not doc:
        # Check if certificate exists but PDF pending.
        cert = db.get(RentalIdentityCertificate, cert_id)
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        raise HTTPException(status_code=202, detail="PDF pending generation")
    file_path = Path(settings.STORAGE_DIR) / doc.pdf_storage_key
    if not file_path.is_file():
        raise HTTPException(status_code=500, detail="Stored PDF missing")
    return StreamingResponse(open(file_path, "rb"), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={file_path.name}"})


@router.post("/{cert_id}/pdf-data")
def download_pdf_data(cert_id: UUID, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Return PDF bytes as JSON so browser download integrations cannot intercept them."""
    _authorize_download(db, cert_id, current_user)
    doc = db.query(CertificateDocument).filter(
        CertificateDocument.certificate_id == cert_id,
        CertificateDocument.is_current == True,
    ).first()
    if not doc:
        cert = db.get(RentalIdentityCertificate, cert_id)
        if not cert:
            raise HTTPException(status_code=404, detail="Certificate not found")
        raise HTTPException(status_code=202, detail="PDF pending generation")
    file_path = Path(settings.STORAGE_DIR) / doc.pdf_storage_key
    if not file_path.is_file():
        raise HTTPException(status_code=500, detail="Stored PDF missing")
    content = file_path.read_bytes()
    db.execute(text("""
        INSERT INTO certificate_delivery_events
            (certificate_id, document_id, actor_id, event_type, delivery_channel, success, metadata)
        VALUES (:certificate, :document, :actor, 'downloaded', 'web', true, '{}'::jsonb)
    """), {"certificate": cert_id, "document": doc.id, "actor": current_user.id})
    db.commit()
    return {"filename": file_path.name, "content_base64": base64.b64encode(content).decode("ascii")}
