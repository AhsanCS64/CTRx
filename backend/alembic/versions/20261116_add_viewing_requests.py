"""Add tenant viewing requests."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261116_viewing_requests"
down_revision = "20261116_property_units"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    status_enum = postgresql.ENUM(
        "pending", "countered", "confirmed", "declined", "expired", "cancelled",
        name="viewing_status",
    )
    status_enum.create(bind, checkfirst=True)
    status_column = postgresql.ENUM(
        "pending", "countered", "confirmed", "declined", "expired", "cancelled",
        name="viewing_status", create_type=False,
    )
    if not sa.inspect(bind).has_table("viewing_requests"):
        op.create_table(
            "viewing_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("proposed_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", status_column, nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant_profiles.user_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["listing_id"], ["listings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "listing_id", name="uq_viewing_tenant_listing"),
        )
    if "idx_viewing_status" not in {index["name"] for index in sa.inspect(bind).get_indexes("viewing_requests")}:
        op.create_index("idx_viewing_status", "viewing_requests", ["status"])


def downgrade() -> None:
    op.drop_index("idx_viewing_status", table_name="viewing_requests")
    op.drop_table("viewing_requests")
    sa.Enum(name="viewing_status").drop(op.get_bind(), checkfirst=True)
