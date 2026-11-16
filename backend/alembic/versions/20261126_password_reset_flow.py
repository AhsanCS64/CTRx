"""Add one-time password reset tokens and session versioning.

Revision ID: 20261126_password_reset
Revises: 20261125_return_local
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20261126_password_reset"
down_revision = "20261125_return_local"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), server_default="0", nullable=False),
    )
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email_digest", sa.String(length=64), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_password_reset_email_created", "password_reset_tokens", ["email_digest", "created_at"])
    op.create_index("ix_password_reset_token_digest", "password_reset_tokens", ["token_digest"], unique=True)


def downgrade():
    op.drop_index("ix_password_reset_token_digest", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_email_created", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("users", "token_version")
