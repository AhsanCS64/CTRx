"""Require landlord confirmation before rent is recorded as paid."""

from alembic import op

revision = "20261118_payment_confirmation"
down_revision = "20261117_rental_offers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_status ADD VALUE IF NOT EXISTS 'submitted'")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION guard_payment_request()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $function$
        BEGIN
            IF OLD.status = 'pending' AND NEW.status IN ('pending', 'submitted', 'cancelled', 'rejected') THEN
                RETURN NEW;
            END IF;
            IF OLD.status = 'submitted' AND NEW.status IN ('accepted', 'rejected') THEN
                RETURN NEW;
            END IF;
            RAISE EXCEPTION 'payment_request % cannot transition from % to %',
                OLD.id, OLD.status, NEW.status;
        END;
        $function$
        """
    )


def downgrade() -> None:
    # PostgreSQL enum labels are intentionally retained to avoid invalidating
    # historical payment rows that may already use the submitted state.
    pass
