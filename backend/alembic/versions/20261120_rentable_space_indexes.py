"""Scope open listing and viewing indexes to the current workflows."""

from alembic import op

revision = "20261120_rentable_indexes"
down_revision = "20261119_workspace"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP INDEX IF EXISTS uq_open_viewing_per_tenant_listing")
    op.execute("DROP INDEX IF EXISTS uq_one_open_listing")
    op.execute("""
        CREATE UNIQUE INDEX uq_open_building_listing ON listings (property_id)
        WHERE unit_id IS NULL AND status IN ('draft', 'available')
    """)
    op.execute("""
        CREATE UNIQUE INDEX uq_open_unit_listing ON listings (unit_id)
        WHERE unit_id IS NOT NULL AND status IN ('draft', 'available')
    """)


def downgrade():
    op.execute("DROP INDEX uq_open_unit_listing")
    op.execute("DROP INDEX uq_open_building_listing")
    op.execute("""
        CREATE UNIQUE INDEX uq_one_open_listing ON listings (property_id)
        WHERE status IN ('draft', 'available')
    """)
