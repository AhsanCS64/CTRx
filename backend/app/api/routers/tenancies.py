"""Tenancy lifecycle endpoints.

Ending a tenancy preserves the original row and changes only its lifecycle
status. A later move is represented by a new tenancy record.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.properties import Property
from app.db.models.tenancies import Tenancy
from app.db.models.users import User
from app.schemas.tenancies import TenancyResponse, TenancyUpdateStatusRequest

router = APIRouter(prefix="/tenancies", tags=["tenancies"])


@router.get("/mine", response_model=list[TenancyResponse])
def list_my_tenancies(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    rows = db.execute(
        select(Tenancy, Property)
        .join(Property, Tenancy.property_id == Property.id)
        .where(Tenancy.tenant_id == user.id)
        .order_by(Tenancy.start_date.desc())
    ).all()
    return [
        TenancyResponse.model_validate(tenancy).model_copy(update={
            "property_address": property_record.address_line,
            "property_type": property_record.property_type,
        })
        for tenancy, property_record in rows
    ]


@router.post("/{tenancy_id}/status", response_model=TenancyResponse)
def update_my_tenancy_status(
    tenancy_id: str,
    payload: TenancyUpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")
    tenancy = db.execute(
        select(Tenancy).where(Tenancy.id == tenancy_id, Tenancy.tenant_id == user.id).with_for_update()
    ).scalar_one_or_none()
    if not tenancy:
        raise HTTPException(status_code=404, detail="Tenancy record not found")
    if tenancy.status != "active":
        raise HTTPException(status_code=409, detail="Only an active tenancy can be ended")
    end_date = payload.end_date or date.today()
    if end_date <= tenancy.start_date:
        raise HTTPException(status_code=400, detail="The end date must be after the tenancy start date")
    tenancy.status = payload.status
    tenancy.end_date = end_date
    db.commit()
    db.refresh(tenancy)
    return tenancy
