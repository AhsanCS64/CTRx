"""Service for the RIC certificate issuance flow (A/B).

The flow follows the specification:

1. **A‑phase (transactional)** – inside a DB transaction the application is
   approved (status ``approved``) and the ``issue_certificate`` stored procedure
   is called. This creates the ``rental_identity_certificates`` row.
2. **B‑phase (outside the transaction)** – after the transaction commits we
   fetch the render data from the ``v_certificate_render_data`` view, generate a
   QR code, render the PDF with the ``CertificateRenderer`` implementation, store
   the file on disk, and finally call ``register_certificate_document`` to create
   a ``certificate_documents`` row. If rendering or storage fails we log the
   failure and leave the certificate without a document (the background job
   ``retry_pending_certificate_pdfs`` will pick it up later).
"""

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Dict, Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from psycopg.types.json import Json

from app.db.models.ric_applications import RicApplication
from app.db.models.rental_identity_certificates import RentalIdentityCertificate
from app.certificates.renderer import render, _generate_qr
from app.certificates.storage import store_pdf
from app.audit import log_action
from app.core.config import settings

RIC_RENDERER = "ctrx-ric-v5"


def _five_years_after(value: datetime) -> datetime:
    """Return the same instant five calendar years later."""
    try:
        return value.replace(year=value.year + 5)
    except ValueError:
        # A leap-day issuance becomes February 28 in the target year.
        return value.replace(year=value.year + 5, day=28)


def _enrich_render_data(db: Session, certificate_id: str, render_data: Dict[str, Any]) -> Dict[str, Any]:
    applicant = db.execute(
        text(
            """
            SELECT a.id AS application_id, a.full_name, a.email, a.date_of_birth, a.identity_last4,
                   a.permanent_address, a.household_address, ar.name AS area_name
            FROM rental_identity_certificates c
            JOIN ric_applications a ON a.id = c.application_id
            JOIN areas ar ON ar.id = a.area_id
            WHERE c.id = :cid
            """
        ),
        {"cid": certificate_id},
    ).mappings().one()
    enriched = dict(render_data)
    enriched.update({
        "full_name": str(applicant["full_name"]).upper(),
        "email": applicant["email"],
        "date_of_birth": applicant["date_of_birth"].isoformat() if applicant["date_of_birth"] else None,
        "identity_last4": applicant["identity_last4"],
        "permanent_address": applicant["permanent_address"],
        "household_address": applicant["household_address"],
        "area_name": applicant["area_name"],
    })
    members = db.execute(
        text(
            """
            SELECT full_name, relationship, date_of_birth
            FROM application_members
            WHERE application_id = :application_id
            ORDER BY full_name
            """
        ),
        {"application_id": applicant["application_id"]},
    ).mappings().all()
    enriched["members"] = [
        {
            "full_name": member["full_name"],
            "relationship": member["relationship"],
            "date_of_birth": member["date_of_birth"].isoformat() if member["date_of_birth"] else None,
        }
        for member in members
    ]
    authority = enriched.get("issuing_authority") or {}
    enriched["official_name"] = authority.get("name") or "Authorized Government Official"
    enriched["official_designation"] = authority.get("designation") or "Central Reviewing Official"
    enriched["signature_name"] = enriched["official_name"].upper()
    issued_at = enriched.get("issued_at")
    if isinstance(issued_at, datetime):
        enriched["issued_at"] = issued_at.isoformat()
        enriched["expires_at"] = _five_years_after(issued_at).isoformat()
    elif issued_at:
        issued_at_value = datetime.fromisoformat(str(issued_at).replace("Z", "+00:00"))
        enriched["issued_at"] = issued_at_value.isoformat()
        enriched["expires_at"] = _five_years_after(issued_at_value).isoformat()
    if enriched.get("status"):
        status_value = str(enriched["status"])
        enriched["status"] = status_value[:1].upper() + status_value[1:].lower()
    return enriched


def issue_certificate_flow(db: Session, app_id: str) -> Dict[str, Any]:
    """Execute the full A/B issuance flow for a RIC application.

    Returns a dict with ``certificate_id`` and ``ric_number``.
    """
    # -------------------- A‑phase (transaction) --------------------
    app = db.get(RicApplication, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.status != "approved":
        raise HTTPException(status_code=400, detail="Application not approved")
    # The DB function ``issue_certificate`` expects the household ID – it is
    # linked via ``households`` which has a FK to the application.
    # Retrieve the household ID first.
    household_id = db.execute(
        text("SELECT id FROM households WHERE application_id = :app_id FOR UPDATE"),
        {"app_id": app_id},
    ).scalar_one()
    # Call the stored procedure – it returns the newly created certificate row.
    cert_row = db.execute(
            text(
                "SELECT * FROM issue_certificate(CAST(:app_id AS uuid), CAST(:household_id AS uuid), CAST(:issued_by AS uuid))"
            ),
        {"app_id": app_id, "household_id": household_id, "issued_by": app.central_reviewed_by},
    ).mappings().first()
    if not cert_row:
        raise HTTPException(status_code=500, detail="Certificate issuance failed")
    certificate_id = cert_row["id"]
    issued_at = db.execute(
        text("SELECT issued_at FROM rental_identity_certificates WHERE id = :cid"),
        {"cid": certificate_id},
    ).scalar_one()
    db.execute(
        text("UPDATE rental_identity_certificates SET expires_at = :expires_at WHERE id = :cid"),
        {"cid": certificate_id, "expires_at": _five_years_after(issued_at)},
    )
    # Audit the issuance (transactional part).
    log_action(
        db,
        action="certificate.issue",
        actor_id=str(app.central_reviewed_by),
        actor_role="government",
        entity_type="rental_identity_certificate",
        entity_id=str(certificate_id),
        metadata={"application_id": app_id},
    )
    db.commit()

    # -------------------- B‑phase (post‑commit) --------------------
    try:
        render_and_register_pdf(db, certificate_id)
    except Exception as exc:
        db.rollback()
        # Rendering or storage failed – leave the certificate without a document.
        # The background job will retry.
        log_action(
            db,
            action="certificate.document.pending",
            actor_id=str(app.central_reviewed_by),
            actor_role="government",
            entity_type="rental_identity_certificate",
            entity_id=str(certificate_id),
            metadata={"error": str(exc)},
        )
        db.commit()
        raise HTTPException(status_code=500, detail="PDF generation failed; certificate marked pending")

    return {"certificate_id": str(certificate_id), "ric_number": cert_row["ric_number"], "status": "active"}


def render_and_register_pdf(db: Session, certificate_id, *, actor=None, upgrade=False) -> bool:
    cert = db.execute(text("""
        SELECT verify_token, issued_by, issued_at, expires_at, status
        FROM rental_identity_certificates WHERE id = :cid FOR UPDATE
    """), {"cid": certificate_id}).mappings().one_or_none()
    if cert is None:
        raise ValueError("Certificate not found")
    renderer = db.execute(text("""
        SELECT renderer FROM certificate_documents WHERE certificate_id = :cid AND is_current
    """), {"cid": certificate_id}).scalar_one_or_none()
    if renderer == RIC_RENDERER or (not upgrade and renderer is not None):
        db.commit()
        return False
    data = db.execute(text("SELECT data FROM v_certificate_render_data WHERE certificate_id = :cid"),
                      {"cid": certificate_id}).scalar_one()
    render_data = _enrich_render_data(db, str(certificate_id), data)
    expires_at = cert["expires_at"]
    render_data["issued_at"] = cert["issued_at"].date().isoformat()
    render_data["expires_at"] = expires_at.date().isoformat() if expires_at else None
    status_value = cert["status"]
    if status_value == "active" and expires_at and expires_at <= datetime.now(timezone.utc):
        status_value = "expired"
    render_data["status"] = status_value.title()
    pdf_bytes = render(render_data, _generate_qr(cert["verify_token"]))
    storage_key = store_pdf(pdf_bytes, prefix="ric")
    try:
        db.execute(text("""
            SELECT register_certificate_document(CAST(:id AS uuid), NULL, CAST(:renderer AS text),
                CAST(:data AS jsonb), CAST(:key AS text), CAST(:sha AS char(64)),
                CAST(:size AS bigint), CAST(:actor AS uuid))
        """), {"id": certificate_id, "renderer": RIC_RENDERER, "data": Json(render_data),
               "key": storage_key, "sha": sha256(pdf_bytes).hexdigest(), "size": len(pdf_bytes),
               "actor": actor.id if actor else cert["issued_by"]})
        log_action(db, "certificate.document.register", actor.id if actor else cert["issued_by"],
                   actor.role if actor else "government", "rental_identity_certificate", certificate_id,
                   metadata={"renderer": RIC_RENDERER})
        db.commit()
    except Exception:
        db.rollback()
        (Path(settings.STORAGE_DIR) / storage_key).unlink(missing_ok=True)
        raise
    return True
