"""Buyer requests, seller decisions, and durable sandbox refund receipts."""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refund_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False, unique=True
        ),
        sa.Column(
            "requested_by_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(8), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decision_revision", sa.Integer(), nullable=True),
        sa.Column(
            "decided_by_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=True
        ),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("merchant_id", sa.String(13), nullable=False),
        sa.Column(
            "capture_id",
            sa.String(64),
            sa.ForeignKey("paypal_checkouts.capture_id"),
            nullable=False,
        ),
        sa.Column("provider_order_id", sa.String(64), nullable=False),
        sa.Column("provider_request_id", sa.String(36), nullable=False, unique=True),
        sa.Column("provider_refund_id", sa.String(64), nullable=True, unique=True),
        sa.Column("provider_status", sa.String(20), nullable=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("lease_token", sa.String(36), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "state IN ('requested', 'denied', 'refund_pending', "
            "'refunded', 'failed', 'needs_review')",
            name="ck_refund_request_state",
        ),
        sa.CheckConstraint("revision >= 1", name="ck_refund_request_revision"),
        sa.CheckConstraint(
            "amount_minor > 0 AND amount_minor <= 100000000000",
            name="ck_refund_request_amount",
        ),
        sa.CheckConstraint(
            "(state = 'requested' AND decision IS NULL) OR "
            "(state = 'denied' AND decision IS NOT NULL "
            "AND decision = 'denied' AND decision_reason IS NOT NULL) OR "
            "(state IN ('refund_pending', 'refunded', 'failed', 'needs_review') "
            "AND decision IS NOT NULL AND decision = 'approved')",
            name="ck_refund_request_decision_state",
        ),
        sa.CheckConstraint(
            "decision IS NULL OR (decided_at IS NOT NULL AND "
            "decided_by_account_id IS NOT NULL AND decision_revision IS NOT NULL)",
            name="ck_refund_request_decision_audit",
        ),
        sa.CheckConstraint(
            "state != 'refunded' OR (provider_refund_id IS NOT NULL AND verified_at IS NOT NULL)",
            name="ck_refund_request_completed",
        ),
        sa.CheckConstraint(
            "(lease_token IS NULL AND lease_expires_at IS NULL) OR "
            "(lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)",
            name="ck_refund_request_lease",
        ),
    )
    op.create_index("ix_refund_request_created", "refund_requests", ["created_at", "id"])


def downgrade():
    count = op.get_bind().execute(sa.text("SELECT COUNT(*) FROM refund_requests")).scalar_one()
    if count:
        raise RuntimeError("Cannot downgrade refund requests while refund records exist.")
    # Fail before any DDL if a wider downgrade would encounter 0009's payment
    # guard. SQLite DDL is not reliably rolled back after a later guard fails.
    payment_count = (
        op.get_bind().execute(sa.text("SELECT COUNT(*) FROM paypal_checkouts")).scalar_one()
    )
    if payment_count:
        raise RuntimeError("Cannot downgrade refund support while payment records exist.")
    op.drop_table("refund_requests")
