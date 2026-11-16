"""Router for government review actions.

- ``GET /government/queue`` – returns pending applications for the authenticated
  government user (local or central). Requires role ``government``.
- ``POST /government/review/{app_id}`` – apply an action (approve/forward/reject)
  on a specific application. The request body follows ``GovernmentReviewRequest``.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_official_level, require_role
from app.db.models.areas import Area
from app.db.models.official_profiles import OfficialProfile
from app.db.models.ric_applications import RicApplication
from app.db.models.rental_identity_certificates import RentalIdentityCertificate
from app.db.models.users import User
from app.schemas.ric import GovernmentReviewRequest
from app.services.government_review import list_queue, review_application

router = APIRouter(prefix="/government", tags=["government"])

# Require the user to have the 'government' role for all endpoints in this router.
require_gov = require_role(["government"])

@router.get("/queue")
def get_queue(
    official: OfficialProfile = Depends(require_official_level()),
    db: Session = Depends(get_db),
    _: User = Depends(require_gov),
):
    """Return pending applications for the current government official.

    The ``require_official_level`` dependency also validates the official profile
    and area for local officials.
    """
    apps = list_queue(db, official)
    area_names = {
        area.id: area.name
        for area in db.execute(
            select(Area).where(Area.id.in_([app.area_id for app in apps]))
        ).scalars()
    }
    return [
        {
            "id": str(app.id),
            "applicant_name": app.full_name,
            "email": app.email,
            "status": app.status,
            "area_id": app.area_id,
            "area_name": area_names.get(app.area_id, "Unknown area"),
            "submitted_at": app.submitted_at,
            "identity_last4": app.identity_last4,
            "rejection_reason": app.rejection_reason,
            "central_note": app.central_note,
        }
        for app in apps
    ]


@router.get("/overview")
def get_overview(
    official: OfficialProfile = Depends(require_official_level()),
    db: Session = Depends(get_db),
    _: User = Depends(require_gov),
):
    """Return the official's profile and workload, scoped to their authority."""
    area = db.get(Area, official.area_id) if official.area_id is not None else None

    applications_query = select(RicApplication.status, func.count()).group_by(RicApplication.status)
    certificates_query = (
        select(func.count())
        .select_from(RentalIdentityCertificate)
        .join(RicApplication, RicApplication.id == RentalIdentityCertificate.application_id)
    )
    if official.level == "local":
        applications_query = applications_query.where(RicApplication.area_id == official.area_id)
        certificates_query = certificates_query.where(RicApplication.area_id == official.area_id)

    status_counts = {
        status_name: count
        for status_name, count in db.execute(applications_query).all()
    }
    certificate_count = db.scalar(certificates_query) or 0

    ready_to_issue = 0
    if official.level == "central":
        ready_to_issue = db.scalar(
            select(func.count())
            .select_from(RicApplication)
            .outerjoin(
                RentalIdentityCertificate,
                RentalIdentityCertificate.application_id == RicApplication.id,
            )
            .where(
                RicApplication.status == "approved",
                RentalIdentityCertificate.id.is_(None),
            )
        ) or 0

    return {
        "official": {
            "full_name": official.full_name,
            "designation": official.designation,
            "level": official.level,
            "area_name": area.name if area else None,
            "district": area.district if area else None,
            "division": area.division if area else None,
        },
        "status_counts": status_counts,
        "pending_review_count": status_counts.get(
            "pending_local" if official.level == "local" else "pending_central", 0
        ),
        "ready_to_issue_count": ready_to_issue,
        "issued_certificate_count": certificate_count,
    }

@router.post("/review/{app_id}")
def review_app(
    app_id: str,
    review: GovernmentReviewRequest,
    official: OfficialProfile = Depends(require_official_level()),
    db: Session = Depends(get_db),
    _: User = Depends(require_gov),
):
    try:
        updated = review_application(db, official, app_id, review)
        db.commit()
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return {"status": updated.status, "app_id": str(updated.id)}
