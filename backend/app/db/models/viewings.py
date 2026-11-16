from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import (ForeignKey, DateTime, Text, Boolean, Enum, func,
                        UniqueConstraint, Index)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ViewingRequest(Base):
    __tablename__ = "viewing_requests"
    __table_args__ = (
        UniqueConstraint("tenant_id", "listing_id", name="uq_viewing_tenant_listing"),
        Index("idx_viewing_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    tenant_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tenant_profiles.user_id"), nullable=False)
    listing_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False)
    proposed_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "countered", "confirmed", "declined", "expired", "cancelled", name="viewing_status"),
        nullable=False,
        server_default="pending",
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confirmed_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    alternative_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column("responded_at", DateTime(timezone=True), nullable=True)
