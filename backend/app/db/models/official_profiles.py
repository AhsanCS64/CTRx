"""SQLAlchemy model for the ``official_profiles`` table.

Maps 1‑to‑1 with ``users.id`` where ``users.role = 'government'``.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, String, Enum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class OfficialProfile(Base):
    __tablename__ = "official_profiles"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    designation: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    level: Mapped[str] = mapped_column(Enum("local", "central", name="official_level"), nullable=False)
    area_id: Mapped[Optional[int]] = mapped_column(ForeignKey("areas.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
