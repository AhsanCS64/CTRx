import logging
from sqlalchemy import text
from app.services.certificate_issuance import render_and_register_pdf

logger = logging.getLogger(__name__)


def run(db) -> dict:
    """Find certificates lacking a document and attempt to render PDFs.
    Returns dict with attempted, succeeded, failed counts.
    """
    attempted = succeeded = failed = 0
    try:
        # Find certificates without a document and with active status
        query = text(
            """
            SELECT c.id FROM rental_identity_certificates c
            LEFT JOIN certificate_documents cd ON cd.certificate_id = c.id
            WHERE cd.id IS NULL AND c.status = 'active'
            """
        )
        result = db.execute(query).fetchall()
        certificate_ids = [row[0] for row in result]
        attempted = len(certificate_ids)
        for cert_id in certificate_ids:
            try:
                render_and_register_pdf(db, cert_id)
                succeeded += 1
            except Exception as e:
                logger.warning('PDF render failed for certificate %s: %s', cert_id, e)
                failed += 1
        logger.info('retry_pdfs completed', extra={
            'attempted': attempted,
            'succeeded': succeeded,
            'failed': failed,
        })
        return {'attempted': attempted, 'succeeded': succeeded, 'failed': failed}
    except Exception as exc:
        logger.exception('retry_pdfs failed')
        raise
