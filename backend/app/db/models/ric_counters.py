"""SQLAlchemy model for the ``ric_counters`` table.

Stores the next sequence value per area for RIC number generation.
"""

from sqlalchemy import Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RicCounter(Base):
    __tablename__ = "ric_counters"
    __table_args__ = (UniqueConstraint("area_id"),)

    area_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
