"""SQLAlchemy model for the ``tenancies`` table.

Matches the schema in ``ctrx_schema_v0.3.sql`` exactly. No extra columns are added.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    ForeignKey,
    Date,
    DateTime,
    Enum,
    Numeric,
    Text,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Enum values must match those defined in the SQL schema.
TenancyStatus = Enum(
    "active",
    "ended",
    "terminated",
    name="tenancy_status",
)

class Tenancy(Base):
    __tablename__ = "tenancies"
    __table_args__ = (
        # Index to help enforce overlapping‑active‑tenancy check.
        Index("idx_tenancy_active", "property_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    property_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False
    )
    unit_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenant_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    landlord_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("landlord_profiles.user_id", ondelete="RESTRICT"), nullable=False
    )
    start_date: Mapped[Date] = mapped_column(Date, nullable=False)
    end_date: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    rent: Mapped[Numeric] = mapped_column("monthly_rent", Numeric(12, 2), nullable=False)
    deposit: Mapped[Numeric] = mapped_column(Numeric(12, 2), nullable=False)
    rent_due_day: Mapped[int] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(TenancyStatus, nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # No cascade deletes – tenancies are immutable for audit purposes.
