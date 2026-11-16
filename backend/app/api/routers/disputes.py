from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.disputes import DisputeCreate, DisputeReview, DisputeResponse
from app.services import disputes as dispute_service
from app.db import models as db_models

router = APIRouter(prefix="/disputes", tags=["disputes"])

@router.post("/", response_model=DisputeResponse, status_code=status.HTTP_201_CREATED)
def create_dispute(
    payload: DisputeCreate,
    db: Session = Depends(deps.get_db),
    user = Depends(deps.get_current_user),
):
    return dispute_service.create_dispute(db, str(user.id), user.role, payload)

@router.get("/", response_model=list[DisputeResponse])
def list_disputes(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(deps.get_db),
    user = Depends(deps.get_current_user),
):
    _, items = dispute_service.list_disputes(db, str(user.id), user.role, skip, limit)
    return items

@router.get("/{dispute_id}", response_model=DisputeResponse)
def get_dispute(
    dispute_id: str,
    db: Session = Depends(deps.get_db),
    user = Depends(deps.get_current_user),
):
    # Use service to fetch and ensure access
    dispute = db.get(db_models.Dispute, dispute_id)
    if not dispute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dispute not found")
    # Party or reviewer access
    if dispute.raised_by != str(user.id) and user.role not in {"admin", "government"}:
        # verify party via service helper
        dispute_service._verify_party(db, str(user.id), user.role, dispute.entity_type, str(dispute.entity_id))
    return dispute_service.DisputeResponse.model_validate(dispute)

@router.patch("/{dispute_id}/review", response_model=DisputeResponse)
def review_dispute(
    dispute_id: str,
    payload: DisputeReview,
    db: Session = Depends(deps.get_db),
    user = Depends(deps.get_current_user),
):
    return dispute_service.review_dispute(db, str(user.id), user.role, dispute_id, payload)
