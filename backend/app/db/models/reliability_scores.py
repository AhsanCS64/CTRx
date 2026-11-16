"""SQLAlchemy model for the ``reliability_scores`` table.

Append-only: DB triggers forbid UPDATE and DELETE on this table.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ReliabilityScore(Base):
    __tablename__ = "reliability_scores"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tenant_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenant_profiles.user_id", ondelete="RESTRICT"),
        nullable=False,
    )
    score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    model_version: Mapped[str] = mapped_column(Text, nullable=False, server_default="v1")
    computed_at: Mapped[datetime] = mapped_column(
        "computed_at",
        "TIMESTAMP WITH TIME ZONE",
        nullable=False,
        server_default=func.now(),
    )
