import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)


def run(db) -> dict:
    """Expire unanswered requests and alternative proposals."""
    try:
        result = db.execute(text("""
            UPDATE viewing_requests SET status = 'expired'
            WHERE status IN ('pending', 'countered') AND expires_at <= now()
        """)).rowcount
        logger.info('expire_viewings completed', extra={'expired_count': result})
        return {'expired_count': result}
    except Exception as exc:
        logger.exception('expire_viewings failed')
        raise
