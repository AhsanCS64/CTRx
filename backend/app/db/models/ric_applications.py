"""SQLAlchemy model for the ``ric_applications`` table.

Exact mapping of the schema; relationships to ``users`` (reviewers) and ``areas`` are expressed via foreign keys.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (Boolean, Date, DateTime, Enum, ForeignKey, String, Text,
                        func, UniqueConstraint, Index, text)
from sqlalchemy.dialects.postgresql import UUID, CITEXT, BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RicApplication(Base):
    __tablename__ = "ric_applications"
    __table_args__ = (
        Index("idx_ric_app_email", "email"),
        Index("idx_ric_app_idhmac", "identity_number_hmac"),
        Index("idx_ric_app_queue", "status", "area_id", "submitted_at"),
        Index("uq_open_application_per_person", "identity_number_hmac",
              unique=True,
              postgresql_where=text("status IN ('pending_local','pending_central')")),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    email: Mapped[str] = mapped_column(CITEXT, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    identity_number_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    identity_number_hmac: Mapped[str] = mapped_column(String, nullable=False)
    identity_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    permanent_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    household_address: Mapped[str] = mapped_column(Text, nullable=False)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    previous_ric_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(Enum(
        "pending_local",
        "pending_central",
        "approved",
        "rejected_local",
        "rejected_central",
        name="ric_app_status",
    ), nullable=False, server_default="pending_local")
    resubmission_of: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("ric_applications.id"), nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    local_reviewed_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    local_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    local_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    central_reviewed_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    central_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    central_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
