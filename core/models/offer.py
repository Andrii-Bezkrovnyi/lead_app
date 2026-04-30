from __future__ import annotations

from uuid import UUID

from sqlalchemy import String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base


class Offer(Base):
    __tablename__ = "offers"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    leads = relationship("Lead", back_populates="offer")
