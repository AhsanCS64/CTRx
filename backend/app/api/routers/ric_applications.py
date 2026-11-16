"""Router for RIC application submission and status retrieval.

- ``POST /ric_applications`` – submit a new application (public, no auth).
- ``GET /ric_applications/{app_id}`` – fetch application status (requires auth, any role).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.db.models.areas import Area
from app.db.models.ric_applications import RicApplication
from app.db.models.users import User
from app.schemas.ric import RicApplicationCreate, RicApplicationResponse, RelocationRequest
import base64
from app.services.ric_application import get_application, submit_application

router = APIRouter(prefix="/ric_applications", tags=["ric_applications"])

@router.get("/areas")
def list_application_areas(db: Session = Depends(get_db)):
    return db.execute(
        select(Area).order_by(Area.division, Area.district, Area.name)
    ).scalars().all()

@router.post("", response_model=RicApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: RicApplicationCreate,
    current_user: User = Depends(require_role(["tenant"])),
    db: Session = Depends(get_db),
):
    payload.email = current_user.email
    app = submit_application(db, payload)
    db.commit()
    return RicApplicationResponse.model_validate(app)

@router.get("/mine", response_model=list[RicApplicationResponse])
def read_my_applications(
    current_user: User = Depends(require_role(["tenant"])),
    db: Session = Depends(get_db),
):
    return db.execute(
        select(RicApplication)
        .where(RicApplication.email == current_user.email)
        .order_by(RicApplication.submitted_at.desc())
    ).scalars().all()

@router.post("/relocate", response_model=RicApplicationResponse, status_code=status.HTTP_201_CREATED)
def relocate_tenant(
    payload: RelocationRequest,
    current_user: User = Depends(require_role(["tenant"])),
    db: Session = Depends(get_db),
):
    """Create a new location application while preserving the previous record."""
    previous = db.execute(
        select(RicApplication)
        .where(RicApplication.email == current_user.email)
        .order_by(RicApplication.submitted_at.desc())
    ).scalars().first()
    if not previous:
        raise HTTPException(status_code=404, detail="Submit an initial RIC application before reporting a move")
    relocation = RicApplicationCreate(
        email=current_user.email,
        full_name=previous.full_name,
        identity_number_enc=base64.b64encode(previous.identity_number_enc).decode(),
        identity_number_hmac=previous.identity_number_hmac,
        identity_last4=previous.identity_last4,
        date_of_birth=previous.date_of_birth,
        permanent_address=payload.permanent_address or previous.permanent_address,
        household_address=payload.household_address,
        area_id=payload.area_id,
        previous_ric_id=str(previous.id),
    )
    app = submit_application(db, relocation)
    db.commit()
    return RicApplicationResponse.model_validate(app)

@router.get("/{app_id}", response_model=RicApplicationResponse)
def read_application(
    app_id: str, current_user=Depends(get_current_user), db: Session = Depends(get_db)
):
    app = get_application(db, app_id)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if current_user.role == "tenant" and app.email != current_user.email:
        raise HTTPException(
            status_code=403, detail="Application access is restricted to its tenant"
        )
    return app
