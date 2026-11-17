"""Record the apartment associated with each tenancy."""

from alembic import op

revision = "20261201_tenancy_apartment"
down_revision = "20261130_monthly_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE property_units ADD CONSTRAINT uq_property_unit_identity UNIQUE (property_id, id);
        ALTER TABLE tenancies ADD COLUMN unit_id uuid;
        ALTER TABLE tenancies ADD CONSTRAINT fk_tenancy_property_unit
            FOREIGN KEY (property_id, unit_id) REFERENCES property_units(property_id, id)
    """)
    op.execute("""
        WITH candidates AS (
            SELECT t.id, (array_agg(DISTINCT l.unit_id))[1] AS unit_id
            FROM tenancies t
            JOIN rental_offers o ON o.tenant_id = t.tenant_id AND o.landlord_id = t.landlord_id
                AND o.status = 'accepted'
            JOIN listings l ON l.id = o.listing_id AND l.property_id = t.property_id
            WHERE o.move_in_date = t.start_date
               OR abs(extract(epoch FROM t.created_at - o.responded_at)) < 60
            GROUP BY t.id
            HAVING count(DISTINCT l.unit_id) = 1 AND bool_and(l.unit_id IS NOT NULL)
        )
        UPDATE tenancies t SET unit_id = c.unit_id FROM candidates c WHERE t.id = c.id
    """)
    op.execute("""
        ALTER TABLE tenancies DROP CONSTRAINT tenancies_property_id_daterange_excl;
        ALTER TABLE tenancies ADD CONSTRAINT tenancies_space_daterange_excl
            EXCLUDE USING gist (
                property_id WITH =, (COALESCE(unit_id, property_id)) WITH =,
                daterange(start_date, COALESCE(end_date, 'infinity'::date), '[)') WITH &&
            ) WHERE (status = 'active');
        CREATE INDEX ix_tenancies_property_unit ON tenancies (property_id, unit_id)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE tenancies DROP CONSTRAINT tenancies_space_daterange_excl;
        ALTER TABLE tenancies ADD CONSTRAINT tenancies_property_id_daterange_excl
            EXCLUDE USING gist (property_id WITH =,
                daterange(start_date, COALESCE(end_date, 'infinity'::date), '[)') WITH &&
            ) WHERE (status = 'active');
        DROP INDEX ix_tenancies_property_unit;
        ALTER TABLE tenancies DROP COLUMN unit_id;
        ALTER TABLE property_units DROP CONSTRAINT uq_property_unit_identity
    """)
