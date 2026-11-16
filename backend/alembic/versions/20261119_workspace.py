"""Persist notifications and sharing grants, and allow viewing rescheduling."""

from alembic import op
import sqlalchemy as sa

revision = "20261119_workspace"
down_revision = "20261118_payment_confirmation"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE workspace_notifications (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            recipient_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            destination text NOT NULL,
            record_id uuid NOT NULL,
            message text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            read_at timestamptz
        )
    """)
    op.execute("CREATE INDEX ON workspace_notifications (recipient_id, id DESC)")
    op.execute("""
        CREATE TABLE rental_history_grants (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            tenant_id uuid NOT NULL REFERENCES users(id),
            landlord_id uuid NOT NULL REFERENCES users(id),
            categories text[] NOT NULL,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        )
    """)
    op.add_column("viewing_requests", sa.Column("alternative_time", sa.DateTime(timezone=True)))
    op.execute("ALTER TABLE viewing_requests ADD COLUMN IF NOT EXISTS responded_at timestamptz")
    op.execute("ALTER TABLE viewing_requests DROP CONSTRAINT IF EXISTS uq_viewing_tenant_listing")
    op.execute("DROP INDEX IF EXISTS uq_viewing_tenant_listing")
    op.execute("""
        CREATE UNIQUE INDEX uq_viewing_tenant_listing ON viewing_requests (tenant_id, listing_id)
        WHERE status IN ('pending', 'countered')
    """)
    op.execute("""
        CREATE FUNCTION notify_workspace_change() RETURNS trigger LANGUAGE plpgsql AS $$
        DECLARE recipient uuid; destination text; message text;
        BEGIN
            IF TG_OP = 'UPDATE' AND NEW.status = OLD.status THEN RETURN NEW; END IF;
            IF TG_TABLE_NAME = 'ric_applications' THEN
                SELECT id INTO recipient FROM users WHERE email = NEW.email AND role = 'tenant';
                destination := 'applications';
                message := 'RIC application: ' || replace(NEW.status::text, '_', ' ');
            ELSIF TG_TABLE_NAME = 'payment_requests' THEN
                destination := 'rent';
                IF NEW.status::text = 'submitted' THEN
                    SELECT landlord_id INTO recipient FROM tenancies WHERE id = NEW.tenancy_id;
                    message := 'A tenant reported a rent payment';
                ELSE
                    SELECT tenant_id INTO recipient FROM tenancies WHERE id = NEW.tenancy_id;
                    message := CASE NEW.status::text
                        WHEN 'pending' THEN 'A new rent invoice is available'
                        WHEN 'accepted' THEN 'Your rent payment was confirmed'
                        ELSE 'Rent invoice: ' || NEW.status::text END;
                END IF;
            ELSE
                recipient := NEW.tenant_id;
                destination := 'viewings';
                message := CASE NEW.status::text WHEN 'countered' THEN 'Your landlord proposed a new viewing time'
                    ELSE 'Viewing request: ' || NEW.status::text END;
            END IF;
            IF recipient IS NOT NULL THEN
                INSERT INTO workspace_notifications (recipient_id, destination, record_id, message)
                VALUES (recipient, destination, NEW.id, message);
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("CREATE TRIGGER notify_ric AFTER INSERT OR UPDATE OF status ON ric_applications FOR EACH ROW EXECUTE FUNCTION notify_workspace_change()")
    op.execute("CREATE TRIGGER notify_rent AFTER INSERT OR UPDATE OF status ON payment_requests FOR EACH ROW EXECUTE FUNCTION notify_workspace_change()")
    op.execute("CREATE TRIGGER notify_viewing AFTER UPDATE OF status ON viewing_requests FOR EACH ROW EXECUTE FUNCTION notify_workspace_change()")


def downgrade():
    op.execute("DROP TRIGGER notify_viewing ON viewing_requests")
    op.execute("DROP TRIGGER notify_rent ON payment_requests")
    op.execute("DROP TRIGGER notify_ric ON ric_applications")
    op.execute("DROP FUNCTION notify_workspace_change()")
    op.drop_index("uq_viewing_tenant_listing", table_name="viewing_requests")
    op.drop_column("viewing_requests", "alternative_time")
    op.drop_table("rental_history_grants")
    op.drop_table("workspace_notifications")
