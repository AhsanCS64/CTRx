"""Allow the invoicing landlord to confirm a reported rent payment.

Revision ID: 20261127_rent_confirmation
Revises: 20261126_password_reset
"""

from alembic import op


revision = "20261127_rent_confirmation"
down_revision = "20261126_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("payment_requests_check1", "payment_requests", type_="check")
    op.create_check_constraint(
        "payment_requests_check1",
        "payment_requests",
        "decided_by IS DISTINCT FROM requested_by OR "
        "(status = 'accepted' AND payment_method IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("payment_requests_check1", "payment_requests", type_="check")
    op.create_check_constraint(
        "payment_requests_check1",
        "payment_requests",
        "decided_by IS DISTINCT FROM requested_by",
    )
