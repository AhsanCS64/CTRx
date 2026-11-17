"""Add monthly tenancy feedback and optional household profile details."""

from alembic import op

revision = "20261130_monthly_feedback"
down_revision = "20261129_tenancy_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE monthly_tenancy_feedback (
            tenancy_id uuid NOT NULL REFERENCES tenancies(id) ON DELETE RESTRICT,
            author_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            period_month date NOT NULL CHECK (EXTRACT(day FROM period_month) = 1),
            category text NOT NULL CHECK (category IN ('communication', 'rent_handling', 'property_care', 'repairs', 'conduct')),
            rating text NOT NULL CHECK (rating IN ('positive', 'satisfactory', 'concern')),
            remark text NOT NULL CHECK (length(trim(remark)) BETWEEN 1 AND 1500),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenancy_id, author_id, period_month, category)
        )
    """)
    op.execute("""
        ALTER TABLE account_profiles
        ADD COLUMN marital_status text CHECK (marital_status IN ('single', 'married', 'other')),
        ADD COLUMN living_arrangement text CHECK (living_arrangement IN ('alone', 'with_family', 'with_partner', 'with_roommates', 'other'))
    """)


def downgrade() -> None:
    op.drop_column("account_profiles", "living_arrangement")
    op.drop_column("account_profiles", "marital_status")
    op.drop_table("monthly_tenancy_feedback")
