"""Initial schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "affiliates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_affiliates_name", "affiliates", ["name"], unique=False)

    op.create_table(
        "offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
    )
    op.create_index("ix_offers_name", "offers", ["name"], unique=False)

    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column(
            "offer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("offers.id", ondelete="RESTRICT"),
            nullable=False
        ),
        sa.Column(
            "affiliate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("affiliates.id", ondelete="RESTRICT"),
            nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_leads_offer_id", "leads", ["offer_id"], unique=False)
    op.create_index("ix_leads_affiliate_id", "leads", ["affiliate_id"], unique=False)
    op.create_index("ix_leads_created_at", "leads", ["created_at"], unique=False)
    op.create_index(
        "ix_leads_affiliate_created_at",
        "leads",
        ["affiliate_id", "created_at"],
        unique=False
    )
    op.create_index(
        "ix_leads_affiliate_offer_created_at",
        "leads",
        ["affiliate_id", "offer_id", "created_at"],
        unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_leads_affiliate_offer_created_at", table_name="leads")
    op.drop_index("ix_leads_affiliate_created_at", table_name="leads")
    op.drop_index("ix_leads_created_at", table_name="leads")
    op.drop_index("ix_leads_affiliate_id", table_name="leads")
    op.drop_index("ix_leads_offer_id", table_name="leads")
    op.drop_table("leads")

    op.drop_index("ix_offers_name", table_name="offers")
    op.drop_table("offers")

    op.drop_index("ix_affiliates_name", table_name="affiliates")
    op.drop_table("affiliates")
