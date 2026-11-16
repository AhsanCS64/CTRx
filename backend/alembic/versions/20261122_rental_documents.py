"""Add lease snapshots, case timeline entries and profile appearance."""

from alembic import op

revision = "20261122_rental_documents"
down_revision = "20261121_account_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE account_profiles ADD COLUMN appearance text NOT NULL DEFAULT 'light', ADD COLUMN theme text NOT NULL DEFAULT 'teal'")
    op.execute("""
        CREATE TABLE lease_agreements (
            tenancy_id uuid PRIMARY KEY REFERENCES tenancies(id),
            terms jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            tenant_acknowledged_at timestamptz,
            landlord_acknowledged_at timestamptz
        )
    """)
    op.execute("""
        CREATE TABLE dispute_timeline (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            dispute_id uuid NOT NULL REFERENCES disputes(id),
            actor_id uuid NOT NULL REFERENCES users(id),
            kind text NOT NULL,
            message text NOT NULL,
            filename text,
            attachment bytea,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE FUNCTION prepare_tenancy_lease() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            INSERT INTO lease_agreements (tenancy_id, terms)
            SELECT NEW.id, jsonb_build_object('property', p.address_line, 'tenant', tp.full_name,
                'landlord', lp.full_name, 'start_date', NEW.start_date, 'monthly_rent', NEW.monthly_rent,
                'deposit', NEW.deposit, 'rent_due_day', NEW.rent_due_day)
            FROM properties p, tenant_profiles tp, landlord_profiles lp
            WHERE p.id = NEW.property_id AND tp.user_id = NEW.tenant_id AND lp.user_id = NEW.landlord_id
            ON CONFLICT (tenancy_id) DO NOTHING;
            RETURN NEW;
        END
        $$
    """)
    op.execute("CREATE TRIGGER prepare_tenancy_lease AFTER INSERT ON tenancies FOR EACH ROW EXECUTE FUNCTION prepare_tenancy_lease()")
    op.execute("CREATE INDEX ON dispute_timeline (dispute_id, id)")


def downgrade():
    op.execute("DROP TRIGGER prepare_tenancy_lease ON tenancies")
    op.execute("DROP FUNCTION prepare_tenancy_lease()")
    op.drop_table("dispute_timeline")
    op.drop_table("lease_agreements")
    op.execute("ALTER TABLE account_profiles DROP COLUMN appearance, DROP COLUMN theme")
