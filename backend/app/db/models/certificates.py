"""SQLAlchemy model for the ``rental_identity_certificates`` table.

Maps exactly to the schema – no extra columns. Uses typed ``Mapped`` fields.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (String, Text, DateTime, func, UniqueConstraint, Enum, ForeignKey)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RentalIdentityCertificate(Base):
    __tablename__ = "rental_identity_certificates"
    __table_args__ = (
        UniqueConstraint("ric_number", name="uq_ric_number"),
        UniqueConstraint("verify_token", name="uq_verify_token"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    ric_number: Mapped[str] = mapped_column(String(12), nullable=False, unique=True)
    verify_token: Mapped[str] = mapped_column(String, nullable=False, unique=True, server_default=func.encode(func.gen_random_bytes(16), "hex"))
    household_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("households.id", ondelete="RESTRICT"), nullable=False, unique=True)
    application_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ric_applications.id", ondelete="RESTRICT"), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(Enum("active", "expired", "revoked", name="ric_status"), nullable=False, server_default="active")
    issued_by: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
