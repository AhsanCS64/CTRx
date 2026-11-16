from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class TenancyCare(Base):
    __tablename__ = "tenancy_care"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=func.gen_random_uuid())
    tenancy_id: Mapped[UUID] = mapped_column(ForeignKey("tenancies.id"))
    kind: Mapped[str] = mapped_column(Text)
    content: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
