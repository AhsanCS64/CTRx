import sys
import traceback
from sqlalchemy import text
from psycopg.types.json import Json
from app.db.session import SessionLocal
from app.certificates.renderer import render, _generate_qr
from app.certificates.storage import store_pdf

CID = sys.argv[1] if len(sys.argv) > 1 else "be12a12a-b36c-47db-be53-bbcfc9d5b890"
db = SessionLocal()
try:
    render_data = db.execute(
        text("SELECT data FROM v_certificate_render_data WHERE certificate_id = :cid"),
        {"cid": CID},
    ).scalar_one()
    print("render_data OK:", type(render_data))
    cert = db.execute(
        text("SELECT verify_token FROM rental_identity_certificates WHERE id = :cid"),
        {"cid": CID},
    ).mappings().first()
    qr_png = _generate_qr(cert["verify_token"])
    pdf_bytes = render(render_data, qr_png)
    print("pdf ok", len(pdf_bytes))
    key = store_pdf(pdf_bytes, prefix="ric")
    print("stored", key)
    db.execute(
        text(
            "SELECT register_certificate_document(CAST(:cert_id AS uuid), CAST(:tmpl_id AS uuid), CAST(:renderer AS text), CAST(:render_data AS jsonb), CAST(:pdf_key AS text), CAST(:pdf_sha AS char(64)), CAST(:size AS bigint), CAST(:generated_by AS uuid))"
        ),
        {
            "cert_id": CID,
            "tmpl_id": None,
            "renderer": "backend",
            "render_data": Json(render_data),
            "pdf_key": key,
            "pdf_sha": "placeholder",
            "size": len(pdf_bytes),
            "generated_by": None,
        },
    )
    db.commit()
    print("registered OK")
except Exception:
    traceback.print_exc()
    db.rollback()
finally:
    db.close()
