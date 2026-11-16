"""Add apartment units under landlord properties.

Revision ID: 20261116_property_units
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20261116_property_units"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "property_units",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("property_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("unit_number", sa.String(length=40), nullable=False),
        sa.Column("floor_number", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("monthly_rent", sa.Numeric(12, 2), nullable=False),
        sa.Column("floor_area_sqft", sa.Numeric(8, 2), nullable=False),
        sa.Column("bedrooms", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("bathrooms", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("available_from", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="available"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["property_id"], ["properties.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("property_id", "unit_number", name="uq_property_unit_number"),
    )
    op.create_index("idx_property_units_property", "property_units", ["property_id", "status"])
    op.add_column(
        "listings",
        sa.Column("unit_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_listings_unit_id",
        "listings",
        "property_units",
        ["unit_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_listings_unit_id", "listings", type_="foreignkey")
    op.drop_column("listings", "unit_id")
    op.drop_index("idx_property_units_property", table_name="property_units")
    op.drop_table("property_units")
