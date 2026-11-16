"""SQLAlchemy model for the ``properties`` table.

Exact mapping of the schema; includes a foreign key to ``landlord_profiles`` and ``areas``.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import TEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Property(Base):
    __tablename__ = "properties"
    __table_args__ = (
        Index("idx_prop_search", "area_id", "monthly_rent", "available_from"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    landlord_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("landlord_profiles.user_id", ondelete="RESTRICT"), nullable=False)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    address_line: Mapped[str] = mapped_column(TEXT, nullable=False)
    property_type: Mapped[str] = mapped_column(Enum(
        "apartment",
        "house",
        "room",
        "studio",
        "duplex",
        "other",
        name="property_type",
    ), nullable=False)
    monthly_rent: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    floor_area_sqft: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    bedrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    bathrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    floor_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    available_from: Mapped[Date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    __table_args__ = (
        UniqueConstraint("id", "landlord_id", name="uq_property_landlord"),
        Index("idx_prop_search", "area_id", "monthly_rent", "available_from"),
    )
