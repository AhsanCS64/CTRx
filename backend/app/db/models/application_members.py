"""SQLAlchemy model for the ``application_members`` table.

Maps to the ``application_members`` table defined in the schema.
"""

from datetime import date
from typing import Optional

from sqlalchemy import (ForeignKey, String, Date, func)
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationMember(Base):
    __tablename__ = "application_members"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    application_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ric_applications.id", ondelete="CASCADE"), nullable=False)
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    relationship: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    identity_number_enc: Mapped[Optional[bytes]] = mapped_column(BYTEA, nullable=True)
    identity_number_hmac: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    identity_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
