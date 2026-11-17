from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Text, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# Status enum matching schema, do not create PostgreSQL type (create_type=False)
DisputeStatusEnum = Enum(
    "open",
    "under_review",
    "resolved",
    "rejected",
    name="dispute_status",
    create_type=False,
)

class Dispute(Base):
    __tablename__ = "disputes"
    __table_args__ = (
        Index("ix_dispute_entity_active", "entity_type", "entity_id", postgresql_where=Column("status").in_(("open", "under_review"))),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    raised_by: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(DisputeStatusEnum, nullable=False, server_default="open")
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
