"""Store shared inspection, maintenance and deposit records."""

from alembic import op

revision = "20261123_tenancy_care"
down_revision = "20261122_rental_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE tenancy_care (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenancy_id uuid NOT NULL REFERENCES tenancies(id),
            kind text NOT NULL CHECK (kind IN ('move_in', 'move_out', 'maintenance', 'deposit')),
            content jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ON tenancy_care (tenancy_id, created_at)")
    op.execute("""
        CREATE UNIQUE INDEX tenancy_care_single_report ON tenancy_care (tenancy_id, kind)
        WHERE kind <> 'maintenance'
    """)


def downgrade():
    op.drop_table("tenancy_care")
