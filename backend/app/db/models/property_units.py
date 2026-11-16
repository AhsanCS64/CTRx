"""Apartment/unit records belonging to a landlord property."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, SmallInteger, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PropertyUnit(Base):
    __tablename__ = "property_units"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    property_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False)
    unit_number: Mapped[str] = mapped_column(String(40), nullable=False)
    floor_number: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    floor_area_sqft: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    bedrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    bathrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    available_from: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="available")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
