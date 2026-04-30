from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(Uuid(
        as_uuid=True),
        primary_key=True,
        default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)
    offer_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("offers.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    affiliate_id: Mapped[UUID] = mapped_column(Uuid(
        as_uuid=True),
        ForeignKey("affiliates.id", ondelete="RESTRICT"),
        nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc), index=True
    )

    offer = relationship("Offer", back_populates="leads")
    affiliate = relationship("Affiliate", back_populates="leads")

    __table_args__ = (
        Index("ix_leads_affiliate_created_at", "affiliate_id", "created_at"),
        Index("ix_leads_affiliate_offer_created_at", "affiliate_id", "offer_id", "created_at"),
    )
