"""SQLAlchemy model for the ``application_documents`` table.

Maps to the ``application_documents`` table defined in the schema.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (ForeignKey, String, Text, func)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ApplicationDocument(Base):
    __tablename__ = "application_documents"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    application_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ric_applications.id", ondelete="CASCADE"), nullable=False)
    doc_type: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(Text, nullable=False, server_default=func.now())
