"""Service functions for government review of RIC applications.

- ``list_queue`` returns applications pending review for the caller's level.
- ``review_application`` applies an action (approve, forward, reject) performed by a
  government user. It updates the appropriate review columns and status, and
  writes an audit log entry.
"""

from datetime import datetime
from typing import List

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.audit import log_action
from app.db.models.certificates import RentalIdentityCertificate
from app.db.models.official_profiles import OfficialProfile
from app.db.models.ric_applications import RicApplication
from app.schemas.ric import GovernmentReviewRequest


def list_queue(db: Session, official: OfficialProfile) -> List[RicApplication]:
    """Return applications that the *official* must act on.

    * Local officials see applications with status ``pending_local`` in their
      ``area_id``.
    * Central officials see applications with status ``pending_central``.
    """
    if official.level == "local":
        stmt = select(RicApplication).where(
            RicApplication.status == "pending_local",
            RicApplication.area_id == official.area_id,
        )
    else:  # central
        stmt = (
            select(RicApplication)
            .outerjoin(
                RentalIdentityCertificate,
                RentalIdentityCertificate.application_id == RicApplication.id,
            )
            .where(
                or_(
                    RicApplication.status == "pending_central",
                    and_(
                        RicApplication.status == "approved",
                        RentalIdentityCertificate.id.is_(None),
                    ),
                )
            )
        )
    return db.execute(stmt).scalars().all()


def review_application(
    db: Session,
    official: OfficialProfile,
    app_id: str,
    review: GovernmentReviewRequest,
) -> RicApplication:
    """Apply a review action to *app_id* by *official*.

    The function enforces the transition rules defined in the DB trigger
    ``guard_ric_application``. It updates the reviewer columns, timestamps, notes
    and changes the ``status`` accordingly.
    """
    app = db.get(RicApplication, app_id)
    if not app:
        raise ValueError("Application not found")

    note = review.note.strip() if review.note and review.note.strip() else None
    if review.action == "reject" and not note:
        raise ValueError("A written reason is required to reject an application")
    if review.action == "return_to_local" and not note:
        raise ValueError("A written reason is required to return an application to local review")

    now = datetime.utcnow()
    if official.level == "local":
        if app.area_id != official.area_id:
            raise PermissionError("Local official out of area")
        if review.action == "forward":
            new_status = "pending_central"
        elif review.action == "reject":
            new_status = "rejected_local"
        elif review.action == "approve":
            # Local cannot approve final; forward to central.
            new_status = "pending_central"
        else:
            raise ValueError("Invalid action")
        app.local_reviewed_by = official.user_id
        app.local_reviewed_at = now
        app.local_note = note
        app.rejection_reason = note if review.action == "reject" else None
        app.status = new_status
    else:  # central
        if review.action == "approve":
            new_status = "approved"
        elif review.action == "reject":
            new_status = "rejected_central"
        elif review.action == "return_to_local":
            new_status = "pending_local"
        else:
            raise ValueError("Central can only approve, reject, or return an application to local review")
        app.central_reviewed_by = official.user_id
        app.central_reviewed_at = now
        app.central_note = note
        app.rejection_reason = note if review.action == "reject" else None
        app.status = new_status

    db.add(app)
    db.flush()
    log_action(
        db,
        action="ric_application.review",
        actor_id=str(official.user_id),
        actor_role="government",
        entity_type="ric_application",
        entity_id=str(app.id),
        metadata={"action": review.action, "note": note},
    )
    return app
