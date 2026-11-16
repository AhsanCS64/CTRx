"""Property and listing endpoints for landlords and tenant discovery."""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.audit import log_action
from app.db.models.listings import Listing
from app.db.models.landlord_profiles import LandlordProfile
from app.db.models.properties import Property
from app.db.models.property_units import PropertyUnit
from app.db.models.users import User
from app.schemas.properties import (
    ListingCreate,
    ListingResponse,
    AvailableListingResponse,
    PropertyCreate,
    PropertyResponse,
    PropertyUnitCreate,
    PropertyUnitResponse,
)

router = APIRouter(prefix="/properties", tags=["properties"])


class ListingUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str | None = None
    status: Literal["draft", "available", "withdrawn"]


def _landlord(user: User) -> None:
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")


@router.get("/mine", response_model=list[PropertyResponse])
def list_my_properties(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _landlord(user)
    return db.execute(select(Property).where(Property.landlord_id == user.id).order_by(Property.created_at.desc())).scalars().all()


@router.get("/available", response_model=list[PropertyResponse])
def list_available_properties(db: Session = Depends(get_db)):
    return db.execute(
        select(Property)
        .join(Listing, Listing.property_id == Property.id)
        .where(Listing.status == "available")
        .order_by(Property.created_at.desc())
    ).scalars().all()


@router.get("/available-listings", response_model=list[AvailableListingResponse])
def list_available_listings(
    area_id: int | None = Query(None, description="Only listings in this registered area"),
    min_rent: Decimal | None = Query(None, ge=0),
    max_rent: Decimal | None = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    filters = [Listing.status == "available"]
    if area_id is not None:
        filters.append(Property.area_id == area_id)
    if min_rent is not None and max_rent is not None and min_rent > max_rent:
        raise HTTPException(400, "Minimum rent must be at most maximum rent")
    rent = func.coalesce(PropertyUnit.monthly_rent, Property.monthly_rent)
    if min_rent is not None:
        filters.append(rent >= min_rent)
    if max_rent is not None:
        filters.append(rent <= max_rent)
    rows = db.execute(
        select(Listing, Property, PropertyUnit)
        .join(Property, Listing.property_id == Property.id)
        .outerjoin(PropertyUnit, Listing.unit_id == PropertyUnit.id)
        .where(*filters)
        .order_by(Listing.created_at.desc())
    ).all()
    return [
        {
            **{column.name: getattr(listing, column.name) for column in Listing.__table__.columns},
            "property_address": property_record.address_line,
            "property_type": property_record.property_type,
            "monthly_rent": float(unit.monthly_rent if unit else property_record.monthly_rent),
            "floor_area_sqft": float(unit.floor_area_sqft if unit else property_record.floor_area_sqft),
            "bedrooms": unit.bedrooms if unit else property_record.bedrooms,
            "bathrooms": unit.bathrooms if unit else property_record.bathrooms,
            "floor_number": unit.floor_number if unit else property_record.floor_number,
            "unit_number": unit.unit_number if unit else None,
        }
        for listing, property_record, unit in rows
    ]


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(payload: PropertyCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _landlord(user)
    if not db.get(LandlordProfile, user.id):
        db.add(LandlordProfile(user_id=user.id, full_name=user.email.split("@", 1)[0]))
        db.flush()
    property_record = Property(landlord_id=user.id, **payload.model_dump())
    db.add(property_record)
    try:
        db.flush()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if "area" in str(exc.orig).lower():
            raise HTTPException(status_code=400, detail="Select a valid area for this property") from exc
        raise HTTPException(status_code=400, detail="Property could not be saved") from exc
    db.refresh(property_record)
    return property_record


@router.get("/{property_id}/units", response_model=list[PropertyUnitResponse])
def list_units(property_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _landlord(user)
    _owned_property(db, property_id, user)
    return db.execute(
        select(PropertyUnit)
        .where(PropertyUnit.property_id == property_id)
        .order_by(PropertyUnit.floor_number, PropertyUnit.unit_number)
    ).scalars().all()


@router.post("/{property_id}/units", response_model=PropertyUnitResponse, status_code=status.HTTP_201_CREATED)
def create_unit(
    property_id: str,
    payload: PropertyUnitCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _landlord(user)
    _owned_property(db, property_id, user)
    duplicate = db.execute(
        select(PropertyUnit).where(
            PropertyUnit.property_id == property_id,
            PropertyUnit.unit_number == payload.unit_number,
        )
    ).scalar_one_or_none()
    if duplicate:
        raise HTTPException(status_code=409, detail="This apartment number already exists in the property")
    unit = PropertyUnit(property_id=property_id, **payload.model_dump())
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return unit


@router.post("/units/{unit_id}/listing", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
def create_unit_listing(
    unit_id: str,
    payload: ListingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _landlord(user)
    unit = db.execute(
        select(PropertyUnit)
        .join(Property, Property.id == PropertyUnit.property_id)
        .where(PropertyUnit.id == unit_id, Property.landlord_id == user.id)
        .with_for_update(of=Property)
    ).scalar_one_or_none()
    if not unit:
        raise HTTPException(status_code=404, detail="Apartment not found for this landlord")
    live = db.execute(
        select(Listing).where(
            Listing.property_id == unit.property_id,
            (Listing.unit_id == unit_id) | Listing.unit_id.is_(None),
            Listing.status.in_(("draft", "available")),
        )
    ).scalars().first()
    if live:
        raise HTTPException(status_code=409, detail="This apartment already has a live listing")
    listing = Listing(
        property_id=unit.property_id,
        unit_id=unit.id,
        status=payload.status or "draft",
        title=payload.title,
        description=payload.description,
        published_at=datetime.now(timezone.utc) if payload.status == "available" else None,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.post("/{property_id}/listing", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
def create_listing(property_id: str, payload: ListingCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _landlord(user)
    property_record = _owned_property(db, property_id, user, lock=True)
    live = db.execute(select(Listing).where(Listing.property_id == property_id, Listing.status.in_(("draft", "available")))).scalars().first()
    if live:
        raise HTTPException(status_code=409, detail="This property already has a live listing")
    listing = Listing(
        property_id=property_record.id,
        status=payload.status or "draft",
        title=payload.title,
        description=payload.description,
        published_at=datetime.now(timezone.utc) if payload.status == "available" else None,
    )
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


def _owned_property(db: Session, property_id: str, user: User, lock: bool = False) -> Property:
    query = select(Property).where(Property.id == property_id, Property.landlord_id == user.id)
    property_record = db.execute(query.with_for_update() if lock else query).scalar_one_or_none()
    if not property_record:
        raise HTTPException(
            status_code=404,
            detail="Property not found for this landlord. Refresh your inventory and try again.",
        )
    return property_record


@router.get("/listings/mine", response_model=list[ListingResponse])
def list_my_listings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _landlord(user)
    return db.execute(
        select(Listing).join(Property, Listing.property_id == Property.id).where(Property.landlord_id == user.id).order_by(Listing.created_at.desc())
    ).scalars().all()


@router.patch("/listings/{listing_id}", response_model=ListingResponse)
def update_listing(listing_id: UUID, payload: ListingUpdate, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    _landlord(user)
    listing = db.execute(select(Listing).join(Property).where(
        Listing.id == listing_id, Property.landlord_id == user.id,
    ).with_for_update(of=Listing)).scalar_one_or_none()
    if listing is None:
        raise HTTPException(404, "Listing not found")
    if listing.status not in {"draft", "available"}:
        raise HTTPException(409, "Only live listings can be edited")
    title = payload.title.strip()
    if not title:
        raise HTTPException(400, "Enter a listing title")
    listing.title = title
    listing.description = payload.description
    listing.status = payload.status
    if payload.status == "available" and listing.published_at is None:
        listing.published_at = datetime.now(timezone.utc)
    log_action(db, "listing.update", user.id, user.role, "listing", listing.id,
               metadata={"status": listing.status})
    db.commit()
    db.refresh(listing)
    return listing
