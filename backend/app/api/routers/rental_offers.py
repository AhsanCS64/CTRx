"""Rental offer and price negotiation endpoints.

- ``POST /rental_offers`` – tenant makes an offer on a listing.
- ``GET /rental_offers/mine`` – tenant's own offers.
- ``GET /rental_offers/landlord`` – offers on the landlord's listings.
- ``POST /rental_offers/{id}/respond`` – landlord accepts, rejects, or counters.
- ``POST /rental_offers/{id}/tenant-respond`` – tenant accepts a counter or counters back.

When an offer is accepted, a ``tenancies`` record is created automatically.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.db.models.listings import Listing
from app.db.models.properties import Property
from app.db.models.rental_offers import RentalOffer
from app.db.models.tenancies import Tenancy
from app.db.models.landlord_profiles import LandlordProfile
from app.db.models.persons import Person
from app.db.models.tenant_profiles import TenantProfile
from app.db.models.users import User
from app.schemas.rental_offers import (
    RentalOfferAction,
    RentalOfferCreate,
    RentalOfferResponse,
)

router = APIRouter(prefix="/rental_offers", tags=["rental_offers"])


def _tenant(user: User) -> None:
    if user.role != "tenant":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant role required")


def _landlord(user: User) -> None:
    if user.role != "landlord":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Landlord role required")


@router.post("", response_model=RentalOfferResponse, status_code=status.HTTP_201_CREATED)
def create_offer(
    payload: RentalOfferCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _tenant(user)
    tenant_profile = db.get(TenantProfile, user.id)
    if not tenant_profile:
        person = Person(full_name=user.email.split("@", 1)[0])
        db.add(person)
        db.flush()
        tenant_profile = TenantProfile(
            user_id=user.id, person_id=person.id, full_name=person.full_name
        )
        db.add(tenant_profile)
        db.flush()

    listing = db.get(Listing, UUID(payload.listing_id))
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.status != "available":
        raise HTTPException(status_code=409, detail="This listing is no longer available")

    property_row = db.get(Property, listing.property_id)
    if not property_row:
        raise HTTPException(status_code=404, detail="Property not found")
    landlord_profile = db.get(LandlordProfile, property_row.landlord_id)

    existing = db.execute(
        select(RentalOffer).where(
            RentalOffer.listing_id == listing.id,
            RentalOffer.tenant_id == user.id,
            RentalOffer.status.in_(["pending", "countered"]),
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="You already have an open offer on this listing",
        )

    offer = RentalOffer(
        listing_id=listing.id,
        tenant_id=user.id,
        landlord_id=property_row.landlord_id,
        proposed_rent=payload.proposed_rent,
        move_in_date=payload.move_in_date,
        message=payload.message,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)

    return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)


@router.get("/mine", response_model=list[RentalOfferResponse])
def list_my_offers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _tenant(user)
    tenant_profile = db.get(TenantProfile, user.id)
    rows = db.execute(
        select(RentalOffer, Listing, Property, LandlordProfile)
        .join(Listing, RentalOffer.listing_id == Listing.id)
        .join(Property, Listing.property_id == Property.id)
        .join(LandlordProfile, Property.landlord_id == LandlordProfile.user_id)
        .where(RentalOffer.tenant_id == user.id)
        .order_by(RentalOffer.created_at.desc())
    ).all()
    return [
        _offer_response(offer, prop, landlord, tenant_profile, db)
        for offer, _listing, prop, landlord in rows
    ]


@router.get("/landlord", response_model=list[RentalOfferResponse])
def list_landlord_offers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _landlord(user)
    landlord_profile = db.get(LandlordProfile, user.id)
    rows = db.execute(
        select(RentalOffer, Listing, Property, TenantProfile)
        .join(Listing, RentalOffer.listing_id == Listing.id)
        .join(Property, Listing.property_id == Property.id)
        .join(TenantProfile, RentalOffer.tenant_id == TenantProfile.user_id)
        .where(Property.landlord_id == user.id)
        .order_by(RentalOffer.created_at.desc())
    ).all()
    return [
        _offer_response(offer, prop, landlord_profile, tenant, db)
        for offer, _listing, prop, tenant in rows
    ]


@router.post("/{offer_id}/respond", response_model=RentalOfferResponse)
def landlord_respond(
    offer_id: str,
    payload: RentalOfferAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _landlord(user)
    if payload.action not in {"accept", "reject", "counter"}:
        raise HTTPException(status_code=400, detail="Action must be accept, reject, or counter")

    offer = db.execute(
        select(RentalOffer)
        .join(Listing, RentalOffer.listing_id == Listing.id)
        .join(Property, Listing.property_id == Property.id)
        .where(RentalOffer.id == offer_id, Property.landlord_id == user.id)
    ).scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer.status not in {"pending", "countered"}:
        raise HTTPException(
            status_code=409, detail="This offer is no longer awaiting a response"
        )

    tenant_profile = db.get(TenantProfile, offer.tenant_id)
    landlord_profile = db.get(LandlordProfile, user.id)
    listing = db.get(Listing, offer.listing_id, with_for_update=True)
    property_row = db.get(Property, listing.property_id) if listing else None

    if payload.action == "accept":
        if not listing or listing.status != "available":
            raise HTTPException(status_code=409, detail="Listing is no longer available")
        offer.status = "accepted"
        offer.landlord_response = payload.response_message or "Offer accepted."
        offer.responded_at = datetime.now(timezone.utc)
        tenancy = Tenancy(
            property_id=listing.property_id,
            tenant_id=offer.tenant_id,
            landlord_id=offer.landlord_id,
            start_date=offer.move_in_date,
            rent=offer.proposed_rent,
            deposit=offer.proposed_rent,
            rent_due_day=1,
            status="active",
        )
        db.add(tenancy)
        if listing:
            listing.status = "rented"
        db.commit()
        db.refresh(offer)
        return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)

    if payload.action == "reject":
        offer.status = "rejected"
        offer.landlord_response = payload.response_message or "Offer rejected."
        offer.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(offer)
        return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)

    # counter
    if not payload.counter_rent:
        raise HTTPException(status_code=400, detail="counter_rent is required when countering")
    offer.status = "countered"
    offer.counter_rent = payload.counter_rent
    offer.landlord_response = payload.response_message or "Counter-offer sent."
    offer.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(offer)
    return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)


@router.post("/{offer_id}/tenant-respond", response_model=RentalOfferResponse)
def tenant_respond(
    offer_id: str,
    payload: RentalOfferAction,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _tenant(user)
    if payload.action not in {"accept", "counter", "withdraw"}:
        raise HTTPException(status_code=400, detail="Action must be accept, counter, or withdraw")

    offer = db.get(RentalOffer, offer_id)
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    if offer.tenant_id != user.id:
        raise HTTPException(status_code=403, detail="Not your offer")
    if payload.action == "withdraw":
        if offer.status not in {"pending", "countered"}:
            raise HTTPException(
                status_code=409, detail="This offer can no longer be withdrawn"
            )
    elif offer.status != "countered":
        raise HTTPException(
            status_code=409, detail="This offer is not awaiting your response"
        )

    tenant_profile = db.get(TenantProfile, user.id)
    landlord_profile = db.get(LandlordProfile, offer.landlord_id)
    listing = db.get(Listing, offer.listing_id, with_for_update=True)
    property_row = db.get(Property, listing.property_id) if listing else None

    if payload.action == "accept":
        if not listing or listing.status != "available":
            raise HTTPException(status_code=409, detail="Listing is no longer available")
        offer.status = "accepted"
        offer.proposed_rent = offer.counter_rent or offer.proposed_rent
        offer.tenant_response = payload.response_message or "Counter-offer accepted."
        offer.responded_at = datetime.now(timezone.utc)
        tenancy = Tenancy(
            property_id=listing.property_id,
            tenant_id=offer.tenant_id,
            landlord_id=offer.landlord_id,
            start_date=offer.move_in_date,
            rent=offer.proposed_rent,
            deposit=offer.proposed_rent,
            rent_due_day=1,
            status="active",
        )
        db.add(tenancy)
        if listing:
            listing.status = "rented"
        db.commit()
        db.refresh(offer)
        return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)

    if payload.action == "withdraw":
        offer.status = "withdrawn"
        offer.tenant_response = payload.response_message or "Offer withdrawn."
        offer.responded_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(offer)
        return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)

    # counter back
    if not payload.counter_rent:
        raise HTTPException(status_code=400, detail="counter_rent is required when countering")
    offer.counter_rent = payload.counter_rent
    offer.tenant_response = payload.response_message or "Counter-offer sent back."
    offer.responded_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(offer)
    return _offer_response(offer, property_row, landlord_profile, tenant_profile, db)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _offer_response(
    offer: RentalOffer,
    property_row: Optional[Property],
    landlord_profile: Optional[LandlordProfile],
    tenant_profile: Optional[TenantProfile],
    db: Session,
) -> dict:
    listing = db.get(Listing, offer.listing_id) if property_row else None
    return {
        **{
            column.name: getattr(offer, column.name)
            for column in RentalOffer.__table__.columns
        },
        "property_address": property_row.address_line if property_row else None,
        "listing_title": listing.title if listing else None,
        "landlord_name": landlord_profile.full_name if landlord_profile else None,
        "tenant_name": tenant_profile.full_name if tenant_profile else None,
    }
