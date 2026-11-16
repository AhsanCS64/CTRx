"""SQLAlchemy model for the ``rental_offers`` table.

A rental offer is a tenant's proposal to rent a listing at a proposed rent.
Landlords can accept, reject, or counter with a different rent. When accepted,
a tenancy record is created automatically.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (Date, DateTime, Enum, ForeignKey, Index, Numeric,
                        Text, func, text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RentalOffer(Base):
    __tablename__ = "rental_offers"
    __table_args__ = (
        Index(
            "uq_rental_offer_tenant_listing_open", "tenant_id", "listing_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'countered')"),
        ),
        Index("idx_rental_offer_listing", "listing_id"),
        Index("idx_rental_offer_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    listing_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    landlord_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlord_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    proposed_rent: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    counter_rent: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "countered", "accepted", "rejected", "withdrawn", "expired",
             name="rental_offer_status"),
        nullable=False, server_default="pending",
    )
    move_in_date: Mapped[date] = mapped_column(Date, nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    landlord_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tenant_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    responded_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )