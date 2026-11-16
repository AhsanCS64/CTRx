"""SQLAlchemy model for the ``payment_requests`` table.

Matches the ctrx DB schema exactly. Uses Mapped[] / mapped_column() style.
DO NOT call create_all() – the table is managed by SQL migrations.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

PaymentStatus = Enum(
    "pending",
    "submitted",
    "accepted",
    "rejected",
    "cancelled",
    name="payment_status",
)


class PaymentRequest(Base):
    __tablename__ = "payment_requests"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenancy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenancies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    requested_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        PaymentStatus, nullable=False, server_default="pending"
    )
    decided_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    decided_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        "submitted_at",
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    payment_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
