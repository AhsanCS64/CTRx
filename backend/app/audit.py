"""Utility for writing audit logs.

The ``log_action`` function inserts a row into the ``audit_logs`` table. It is
intended to be called by services whenever a state‑changing operation occurs.
All fields are optional except ``action``; ``metadata`` defaults to an empty
JSON object. ``ip_address`` can be passed from a request if needed.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import insert, text

from app.db.models.audit_logs import AuditLog

def log_action(
    db: Session,
    action: str,
    actor_id: Optional[str] = None,
    actor_role: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Insert an audit log entry.

    ``metadata`` is stored as JSONB – callers should pass a plain‑dict that can
    be JSON‑serialised.
    """
    if metadata is None:
        metadata = {}
    entry = AuditLog(
        actor_id=actor_id,
        actor_role=actor_role,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
        ip_address=ip_address,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    # The caller is responsible for committing the transaction.
