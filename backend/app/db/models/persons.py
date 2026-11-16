"""SQLAlchemy model for the ``persons`` table.

Maps directly to the schema defined in ``ctrx_schema_v0.3.sql``. Uses the
typed ``Mapped`` style required by SQLAlchemy 2.x.
"""

from typing import Optional
from sqlalchemy import String, Date, DateTime, Text, func
import datetime
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Person(Base):
    __tablename__ = "persons"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    full_name: Mapped[str] = mapped_column(String, nullable=False)
    identity_number_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=True)
    identity_number_hmac: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    identity_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    date_of_birth: Mapped[Optional[Date]] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
