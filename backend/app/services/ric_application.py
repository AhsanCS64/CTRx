"""Service functions for RIC applications.

- ``submit_application``: creates a new ``RicApplication`` row from the
  ``RicApplicationCreate`` schema. The payload includes encrypted identity
  fields; the service does **not** perform any encryption – the caller provides
  already‑encrypted data as required by the SRS.
- ``get_application``: fetches an application by its UUID and returns a
  ``RicApplicationResponse`` Pydantic model.

Both functions write an audit log entry via ``audit.log_action``.
"""

import base64
import hashlib
import hmac
from datetime import datetime
from typing import Optional

from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.core.config import settings
from app.db.models.households import Household
from app.db.models.application_members import ApplicationMember
from app.db.models.ric_applications import RicApplication
from app.schemas.ric import RicApplicationCreate, RicApplicationResponse


def submit_application(db: Session, payload: RicApplicationCreate) -> RicApplication:
    """Insert a new RIC application.

    The caller must provide encrypted ``identity_number_enc`` and the HMAC. The
    function does **not** encrypt or hash anything – the heavy‑lifting is done
    by the client or a separate utility.
    """
    identity_number = payload.identity_number
    if identity_number:
        identity_hmac = hmac.new(
            settings.HMAC_SECRET.encode(), identity_number.strip().encode(), hashlib.sha256
        ).hexdigest()
        identity_enc = base64.b64encode(
            Fernet(settings.ENCRYPTION_KEY.encode()).encrypt(identity_number.strip().encode())
        )
    else:
        identity_hmac = payload.identity_number_hmac
        identity_enc = base64.b64decode(payload.identity_number_enc or "")

    new_app = RicApplication(
        email=payload.email,
        full_name=payload.full_name,
        identity_number_enc=identity_enc,
        identity_number_hmac=identity_hmac,
        identity_last4=(
            payload.identity_last4 or (identity_number[-4:] if identity_number else None)
        ),
        date_of_birth=payload.date_of_birth,
        permanent_address=payload.permanent_address,
        household_address=payload.household_address,
        area_id=payload.area_id,
        previous_ric_id=payload.previous_ric_id,
        status="pending_local",
        submitted_at=datetime.utcnow(),
    )
    db.add(new_app)
    db.flush()  # obtain PK for the linked household
    for member in payload.members:
        db.add(ApplicationMember(
            application_id=new_app.id,
            full_name=member.full_name,
            relationship=member.relationship,
            date_of_birth=member.date_of_birth,
        ))
    # Every RIC application gets its linked household (SRS: one household per app).
    household = Household(
        application_id=new_app.id,
        area_id=payload.area_id,
        household_address=payload.household_address,
        permanent_address=payload.permanent_address,
    )
    db.add(household)
    db.flush()  # obtain PK for audit
    log_action(
        db,
        action="ric_application.submit",
        actor_id=None,
        actor_role=None,
        entity_type="ric_application",
        entity_id=str(new_app.id),
        metadata=payload.model_dump(
            mode="json",
            exclude={"identity_number", "identity_number_enc", "identity_number_hmac"},
        ),
    )
    return new_app


def get_application(db: Session, app_id: str) -> Optional[RicApplicationResponse]:
    stmt = select(RicApplication).where(RicApplication.id == app_id)
    result = db.execute(stmt).scalar_one_or_none()
    if not result:
        return None
    # Map to Pydantic response (orm_mode enabled)
    return RicApplicationResponse.model_validate(result)
