from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base


class Affiliate(Base):
    __tablename__ = "affiliates"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True,
                                     default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    leads = relationship("Lead", back_populates="affiliate")
