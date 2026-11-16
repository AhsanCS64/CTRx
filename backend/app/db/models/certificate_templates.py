"""SQLAlchemy model for the ``certificate_templates`` table.

Represents a versioned template used to render RIC PDFs.
"""

import datetime
from typing import Optional

from sqlalchemy import Boolean, JSON, String, func, UniqueConstraint, Index, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CertificateTemplate(Base):
    __tablename__ = "certificate_templates"
    __table_args__ = (
        UniqueConstraint("code", "version", name="uq_certificate_template_code_version"),
        Index("uq_one_default_template", "is_default", unique=True, postgresql_where="is_default"),
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    code: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    name: Mapped[str] = mapped_column(String, nullable=False)
    renderer: Mapped[str] = mapped_column(String, nullable=False, server_default="backend")
    config: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    asset_storage_key: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="FALSE")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="TRUE")
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
