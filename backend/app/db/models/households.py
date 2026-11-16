"""SQLAlchemy model for the ``households`` table.

Maps directly to the schema; each household is linked to a single RIC application.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (ForeignKey, String, Text, DateTime, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Household(Base):
    __tablename__ = "households"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    application_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ric_applications.id"), nullable=False, unique=True)
    area_id: Mapped[int] = mapped_column(ForeignKey("areas.id"), nullable=False)
    household_address: Mapped[str] = mapped_column(Text, nullable=False)
    permanent_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
