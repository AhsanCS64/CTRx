"""SQLAlchemy model for the ``landlord_profiles`` table.

One‑to‑one with ``users.id`` where ``users.role = 'landlord'``.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LandlordProfile(Base):
    __tablename__ = "landlord_profiles"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    phone_enc: Mapped[Optional[bytes]] = mapped_column(BYTEA, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
