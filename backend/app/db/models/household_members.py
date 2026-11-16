"""SQLAlchemy model for the ``household_members`` table.

Maps to the ``household_members`` table; includes foreign keys to ``households`` and ``persons``.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (ForeignKey, String, DateTime, Enum, func, UniqueConstraint, Index, text)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class HouseholdMember(Base):
    __tablename__ = "household_members"
    __table_args__ = (
        Index("uq_person_one_active_household", "person_id",
              unique=True,
              postgresql_where=text("left_at IS NULL")),
        Index("uq_household_one_active_primary", "household_id",
              unique=True,
              postgresql_where=text("member_role = 'primary_holder' AND left_at IS NULL")),
        Index("idx_household_members_household", "household_id"),
        Index("idx_household_members_person", "person_id"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    household_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("households.id"), nullable=False)
    person_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("persons.id"), nullable=False)
    member_role: Mapped[str] = mapped_column(Enum("primary_holder", "member", name="household_member_role"), nullable=False, server_default="member")
    relationship: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    left_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
