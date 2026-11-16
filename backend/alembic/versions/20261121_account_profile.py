"""Add self-service account profile settings."""

from alembic import op
import sqlalchemy as sa

revision = "20261121_account_profile"
down_revision = "20261120_rentable_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "account_profiles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("display_name", sa.String(100)),
        sa.Column("contact_phone_enc", sa.LargeBinary()),
        sa.Column("photo", sa.LargeBinary()),
    )


def downgrade():
    op.drop_table("account_profiles")
