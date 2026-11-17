"""Store structured feedback from each party on a tenancy."""

from alembic import op

revision = "20261129_tenancy_feedback"
down_revision = "20261128_reliability_missed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE tenancy_feedback (
            tenancy_id uuid NOT NULL REFERENCES tenancies(id) ON DELETE RESTRICT,
            author_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
            category text NOT NULL CHECK (category IN ('communication', 'rent_handling', 'property_care', 'repairs', 'conduct')),
            rating text NOT NULL CHECK (rating IN ('positive', 'satisfactory', 'concern')),
            remark text NOT NULL CHECK (length(trim(remark)) BETWEEN 1 AND 1500),
            updated_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (tenancy_id, author_id, category)
        )
    """)


def downgrade() -> None:
    op.drop_table("tenancy_feedback")
