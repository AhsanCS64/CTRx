"""SQLAlchemy model for the ``certificate_documents`` table.

Tracks generated PDF documents for a certificate.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, JSON, String, Text, UniqueConstraint, Index, func, DateTime, Integer, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CertificateDocument(Base):
    __tablename__ = "certificate_documents"
    __table_args__ = (
        UniqueConstraint("certificate_id", "version", name="uq_certificate_document_version"),
        Index("uq_cert_one_current_document", "certificate_id", unique=True, postgresql_where="is_current"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    certificate_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("rental_identity_certificates.id", ondelete="RESTRICT"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    template_id: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("certificate_templates.id"), nullable=True)
    renderer: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    render_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    pdf_storage_key: Mapped[str] = mapped_column(String, nullable=False)
    pdf_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="TRUE")
    generated_by: Mapped[Optional[UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
