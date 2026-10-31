"""Durable shared-merchant sandbox checkout and verified capture receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "paypal_checkouts",
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), primary_key=True),
        sa.Column("merchant_id", sa.String(13), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("create_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("capture_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("provider_order_id", sa.String(64), nullable=True, unique=True),
        sa.Column("provider_status", sa.String(32), nullable=True),
        sa.Column("capture_started_at", sa.DateTime(), nullable=True),
        sa.Column("capture_id", sa.String(64), nullable=True, unique=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("fee_minor", sa.Integer(), nullable=True),
        sa.Column("net_minor", sa.Integer(), nullable=True),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "state IN ('creating', 'ready', 'capture_pending', "
            "'completed', 'failed', 'needs_review')",
            name="ck_paypal_checkout_state",
        ),
        sa.CheckConstraint(
            "amount_minor > 0 AND amount_minor <= 100000000000",
            name="ck_paypal_checkout_amount",
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_paypal_checkout_lease",
        ),
        sa.CheckConstraint(
            "state != 'completed' OR (capture_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_paypal_checkout_completed",
        ),
    )


def downgrade():
    # Deleting request IDs/receipts could make an already captured order payable
    # again after re-upgrade. Financial attempts require an explicit recovery plan.
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM paypal_checkouts")).scalar_one()
    if count:
        raise RuntimeError("Cannot downgrade PayPal checkout while payment records exist.")
    op.drop_table("paypal_checkouts")
