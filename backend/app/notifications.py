import json
import logging
import app.audit as audit

logger = logging.getLogger(__name__)

class NotificationService:
    def notify(self, db, event_type: str, user_id: str, payload: dict):
        """Log a notification event and write an audit entry.
        No database table is created; this relies on structured logging and
        the existing audit system.
        """
        # Structured log line
        logger.info(
            'NOTIFICATION event=%s user=%s payload=%s',
            event_type,
            user_id,
            json.dumps(payload, separators=(',', ':')),
        )
        # Audit entry
        audit.log_action(
            db,
            f'notification.{event_type}',
            actor_id=None,
            entity_type='notification',
            metadata=payload,
        )

# Singleton instance for the application
notification_service = NotificationService()
