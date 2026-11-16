"""Add rental offers for tenant-landlord price negotiation.

Revision ID: 20261117_rental_offers
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261117_rental_offers"
down_revision = "20261116_viewing_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    status_enum = postgresql.ENUM(
        "pending", "countered", "accepted", "rejected", "withdrawn", "expired",
        name="rental_offer_status",
    )
    status_enum.create(bind, checkfirst=True)
    status_column = postgresql.ENUM(
        "pending", "countered", "accepted", "rejected", "withdrawn", "expired",
        name="rental_offer_status", create_type=False,
    )
    if not sa.inspect(bind).has_table("rental_offers"):
        op.create_table(
            "rental_offers",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("landlord_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("proposed_rent", sa.Numeric(12, 2), nullable=False),
            sa.Column("counter_rent", sa.Numeric(12, 2), nullable=True),
            sa.Column("status", status_column, nullable=False, server_default="pending"),
            sa.Column("move_in_date", sa.Date(), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("landlord_response", sa.Text(), nullable=True),
            sa.Column("tenant_response", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenant_profiles.user_id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["landlord_id"], ["landlord_profiles.user_id"], ondelete="RESTRICT"),
        )
        op.create_index("idx_rental_offer_listing", "rental_offers", ["listing_id"])
        op.create_index("idx_rental_offer_status", "rental_offers", ["status"])
    if "uq_rental_offer_tenant_listing_open" not in {index["name"] for index in sa.inspect(bind).get_indexes("rental_offers")}:
        op.execute(
            "CREATE UNIQUE INDEX uq_rental_offer_tenant_listing_open ON rental_offers (tenant_id, listing_id) "
            "WHERE status IN ('pending', 'countered')"
        )


def downgrade() -> None:
    op.drop_index("uq_rental_offer_tenant_listing_open", table_name="rental_offers", postgresql_where=sa.text("status IN ('pending', 'countered')"))
    op.drop_index("idx_rental_offer_status", table_name="rental_offers")
    op.drop_index("idx_rental_offer_listing", table_name="rental_offers")
    op.drop_table("rental_offers")
    sa.Enum(name="rental_offer_status").drop(op.get_bind(), checkfirst=True)