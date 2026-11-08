"""Private append-only local pickup reports, separate from financial state."""

import sqlalchemy as sa
from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "pickup_fulfillment_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("pickup_instructions", sa.Text(), nullable=True),
        sa.Column(
            "recorded_by_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_id", "revision", name="uq_pickup_order_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_pickup_revision"),
        sa.CheckConstraint(
            "state IN ('preparing', 'ready_for_pickup', 'collected')", name="ck_pickup_state"
        ),
        sa.CheckConstraint(
            "pickup_instructions IS NULL OR length(pickup_instructions) BETWEEN 1 AND 2000",
            name="ck_pickup_instructions",
        ),
        sa.CheckConstraint(
            "state = 'preparing' OR pickup_instructions IS NOT NULL",
            name="ck_pickup_ready_instructions",
        ),
    )


def downgrade():
    for table, label in (
        ("pickup_fulfillment_events", "pickup history"),
        ("product_photos", "photo"),
        ("refund_requests", "refund"),
        ("paypal_checkouts", "payment"),
        ("order_sales_cost_snapshots", "sales cost snapshot"),
        ("product_sales_cost_bases", "selected cost basis"),
        ("supplier_comparisons", "sourcing"),
        ("supplier_quotes", "sourcing"),
        ("sourcing_inputs", "sourcing"),
        ("favorites", "favorite"),
        ("storefronts", "storefront"),
    ):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"Cannot downgrade fulfillment while {label} records exist.")
    op.drop_table("pickup_fulfillment_events")
