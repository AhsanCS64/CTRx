"""SQLAlchemy model for the ``tenant_profiles`` table.

Exact mapping of the schema – one‑to‑one with ``users.id`` where ``users.role`` is ``tenant``.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenantProfile(Base):
    __tablename__ = "tenant_profiles"

    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    person_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="RESTRICT"), unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    phone_enc: Mapped[Optional[bytes]] = mapped_column(BYTEA, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
