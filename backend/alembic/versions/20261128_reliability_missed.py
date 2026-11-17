"""Link verified missed-payment events to a rental period."""

from alembic import op
import sqlalchemy as sa

revision = "20261128_reliability_missed"
down_revision = "20261127_rent_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reliability_score_events", sa.Column("period_month", sa.Date(), nullable=True))
    op.create_index(
        "uq_reliability_missed_period", "reliability_score_events", ["tenancy_id", "period_month"],
        unique=True, postgresql_where=sa.text("event_type = 'missed' AND period_month IS NOT NULL"),
    )


def downgrade() -> None:
    # Keep the original append-only event and snapshot if the attribution is removed.
    op.drop_index("uq_reliability_missed_period", table_name="reliability_score_events")
    op.drop_column("reliability_score_events", "period_month")
