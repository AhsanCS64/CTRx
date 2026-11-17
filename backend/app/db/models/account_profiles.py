from uuid import UUID

from sqlalchemy import ForeignKey, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AccountProfile(Base):
    __tablename__ = "account_profiles"

    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100))
    marital_status: Mapped[str | None] = mapped_column(String)
    living_arrangement: Mapped[str | None] = mapped_column(String)
    contact_phone_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    photo: Mapped[bytes | None] = mapped_column(LargeBinary)
    appearance: Mapped[str] = mapped_column(String, server_default="light")
    theme: Mapped[str] = mapped_column(String, server_default="teal")
