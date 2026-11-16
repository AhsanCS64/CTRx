"""SQLAlchemy model for the ``areas`` table.

Maps exactly to the schema defined in ``ctrx_schema_v0.3.sql`` – no extra
columns. Uses the typed ``Mapped[...]`` style required by SQLAlchemy 2.x.
"""

from sqlalchemy import Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Area(Base):
    __tablename__ = "areas"
    __table_args__ = (
        UniqueConstraint("division_code", "district_code", "upazila_code"),
        UniqueConstraint("division", "district", "name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    division: Mapped[str] = mapped_column(String, nullable=False)
    division_code: Mapped[str] = mapped_column(String(2), nullable=False)
    district: Mapped[str] = mapped_column(String, nullable=False)
    district_code: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # Upazila/Thana name
    upazila_code: Mapped[str] = mapped_column(String(3), nullable=False)
