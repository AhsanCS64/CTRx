"""Tenant viewing requests and viewing history."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.areas import Area
from app.db.models.listings import Listing
from app.db.models.properties import Property
from app.db.models.property_units import PropertyUnit
from app.db.models.users import User
from app.db.models.viewings import ViewingRequest
from app.db.models.landlord_profiles import LandlordProfile
from app.db.models.tenant_profiles import TenantProfile
from app.db.models.persons import Person
from app.schemas.viewings import ViewingCreateRequest, ViewingResponse, ViewingStatusUpdate

router = APIRouter(prefix="/viewings", tags=["viewings"])


def _tenant(user: User) -> None:
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")


@router.post("", response_model=ViewingResponse, status_code=status.HTTP_201_CREATED)
def create_viewing(
    payload: ViewingCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _tenant(user)
    if not db.get(TenantProfile, user.id):
        person = Person(full_name=user.email.split("@", 1)[0])
        db.add(person)
        db.flush()
        db.add(TenantProfile(user_id=user.id, person_id=person.id, full_name=person.full_name))
        db.flush()
    if payload.proposed_time <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Choose a future date and time for the viewing")
    listing = db.execute(
        select(Listing).where(Listing.id == UUID(payload.listing_id), Listing.status == "available")
    ).scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="This listing is no longer available")
    db.execute(update(ViewingRequest).where(
        ViewingRequest.tenant_id == user.id, ViewingRequest.listing_id == listing.id,
        ViewingRequest.status.in_(("pending", "countered")), ViewingRequest.expires_at <= func.now(),
    ).values(status="expired"))
    request_record = ViewingRequest(
        tenant_id=user.id,
        listing_id=listing.id,
        proposed_time=payload.proposed_time,
        message=payload.message,
        expires_at=min(payload.proposed_time, datetime.now(timezone.utc) + timedelta(days=7)),
    )
    db.add(request_record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "uq_viewing_tenant_listing" in str(exc.orig):
            raise HTTPException(status_code=409, detail="You already requested a viewing for this listing") from exc
        raise HTTPException(status_code=400, detail="Viewing request could not be saved") from exc
    db.refresh(request_record)
    return request_record


@router.get("/mine", response_model=list[ViewingResponse])
def list_my_viewings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _tenant(user)
    rows = db.execute(
        select(ViewingRequest, Listing, Property, PropertyUnit, LandlordProfile, Area)
        .join(Listing, ViewingRequest.listing_id == Listing.id)
        .join(Property, Listing.property_id == Property.id)
        .join(Area, Area.id == Property.area_id)
        .outerjoin(PropertyUnit, Listing.unit_id == PropertyUnit.id)
        .join(LandlordProfile, Property.landlord_id == LandlordProfile.user_id)
        .where(ViewingRequest.tenant_id == user.id)
        .order_by(ViewingRequest.created_at.desc())
    ).all()
    return [
        {
            **{
                column.name: getattr(viewing, column.name)
                for column in ViewingRequest.__table__.columns
                if column.name != "responded_at"
            },
            "updated_at": viewing.updated_at,
            "status": _visible_status(viewing),
            "property_address": property_record.address_line,
            "area_name": area.name,
            "district": area.district,
            "division": area.division,
            "property_type": property_record.property_type,
            "unit_number": unit.unit_number if unit else None,
            "monthly_rent": float(unit.monthly_rent if unit else property_record.monthly_rent),
            "listing_title": listing.title,
            "landlord_name": landlord.full_name,
        }
        for viewing, listing, property_record, unit, landlord, area in rows
    ]


@router.get("/landlord", response_model=list[ViewingResponse])
def list_landlord_viewings(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _landlord(user)
    rows = db.execute(
        select(ViewingRequest, Listing, Property, PropertyUnit, LandlordProfile, TenantProfile, Area)
        .join(Listing, ViewingRequest.listing_id == Listing.id)
        .join(Property, Listing.property_id == Property.id)
        .join(Area, Area.id == Property.area_id)
        .outerjoin(PropertyUnit, Listing.unit_id == PropertyUnit.id)
        .join(LandlordProfile, Property.landlord_id == LandlordProfile.user_id)
        .join(TenantProfile, ViewingRequest.tenant_id == TenantProfile.user_id)
        .where(Property.landlord_id == user.id)
        .order_by(ViewingRequest.created_at.desc())
    ).all()
    return [
        {
            **{
                column.name: getattr(viewing, column.name)
                for column in ViewingRequest.__table__.columns
                if column.name != "responded_at"
            },
            "updated_at": viewing.updated_at,
            "status": _visible_status(viewing),
            "property_address": property_record.address_line,
            "area_name": area.name,
            "district": area.district,
            "division": area.division,
            "property_type": property_record.property_type,
            "unit_number": unit.unit_number if unit else None,
            "monthly_rent": float(unit.monthly_rent if unit else property_record.monthly_rent),
            "listing_title": listing.title,
            "landlord_name": landlord.full_name,
            "tenant_name": tenant.full_name,
        }
        for viewing, listing, property_record, unit, landlord, tenant, area in rows
    ]


def _landlord(user: User) -> None:
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")


def _visible_status(viewing: ViewingRequest) -> str:
    if viewing.status in {"pending", "countered"} and viewing.expires_at <= datetime.now(timezone.utc):
        return "expired"
    return viewing.status


@router.post("/{viewing_id}/status", response_model=ViewingResponse)
def update_viewing_status(
    viewing_id: str,
    payload: ViewingStatusUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    landlord = user.role == "landlord"
    if not landlord:
        _tenant(user)
    allowed = {"confirmed", "declined", "countered"} if landlord else {"confirmed", "declined"}
    if payload.status not in allowed:
        raise HTTPException(status_code=400, detail="Invalid viewing action")
    owner = Property.landlord_id == user.id if landlord else ViewingRequest.tenant_id == user.id
    row = db.execute(
        select(ViewingRequest)
        .join(Listing, ViewingRequest.listing_id == Listing.id)
        .join(Property, Listing.property_id == Property.id)
        .where(ViewingRequest.id == viewing_id, owner)
        .with_for_update(of=ViewingRequest)
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Viewing request not found")
    now = datetime.now(timezone.utc)
    if row.status != ("pending" if landlord else "countered") or row.expires_at <= now:
        raise HTTPException(status_code=409, detail="This viewing request is no longer awaiting a response")
    scheduled_time = row.proposed_time if landlord else row.alternative_time
    if payload.status == "countered":
        if payload.alternative_time is None or payload.alternative_time <= now:
            raise HTTPException(400, "Choose a future alternative time")
        row.alternative_time = payload.alternative_time
        row.expires_at = min(payload.alternative_time, now + timedelta(days=7))
    if payload.status == "confirmed" and (scheduled_time is None or scheduled_time <= now):
        raise HTTPException(409, "This viewing time has passed")
    row.status = payload.status
    row.confirmed_time = scheduled_time if payload.status == "confirmed" else None
    row.updated_at = now
    log_action(db, f"viewing.{row.status}", user.id, user.role, "viewing_request", row.id)
    db.commit()
    db.refresh(row)
    return row
