"""SQLAlchemy model for the ``ledger_entries`` table.

The table is **append-only**: DB triggers forbid UPDATE and DELETE. Never call
db.delete() on these rows. IntegrityError with 'forbid_mutation' in the message
should be mapped to HTTP 409 ERR_LEDGER_IMMUTABLE by the service layer.
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

LedgerEntryType = Enum(
    "payment",
    "correction",
    name="ledger_entry_type",
)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenancy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenancies.id", ondelete="RESTRICT"),
        nullable=False,
    )
    entry_type: Mapped[str] = mapped_column(LedgerEntryType, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_request_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("payment_requests.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    corrects_entry_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ledger_entries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    correction_reason: Mapped[Optional[str]] = mapped_column("reason", Text, nullable=True)
    period_month: Mapped[date] = mapped_column(Date, nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        "actor_id",
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
