"""Allow tenants to share RIC certificates with landlords."""

from alembic import op

revision = "20261124_ric_consent_scope"
down_revision = "20261123_tenancy_care"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE grant_scope ADD VALUE IF NOT EXISTS 'ric_certificate'")


def downgrade():
    # PostgreSQL cannot remove an enum value without rebuilding dependent columns.
    pass
