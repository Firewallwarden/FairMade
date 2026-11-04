"""Explicit seller cost selections and private immutable order cost snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_sales_cost_bases",
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.String(36), sa.ForeignKey("analyses.id"), nullable=True),
        sa.Column("source_snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.CheckConstraint("revision >= 0", name="ck_product_sales_cost_basis_revision"),
        sa.CheckConstraint(
            "(analysis_id IS NULL AND source_snapshot IS NULL) OR "
            "(analysis_id IS NOT NULL AND source_snapshot IS NOT NULL)",
            name="ck_product_sales_cost_basis_source",
        ),
    )
    op.create_table(
        "order_sales_cost_snapshots",
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("estimated_cost", sa.String(100), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "status IN ('available', 'unavailable')", name="ck_order_sales_cost_snapshot_status"
        ),
        sa.CheckConstraint(
            "(status = 'available' AND estimated_cost IS NOT NULL) OR "
            "(status = 'unavailable' AND estimated_cost IS NULL)",
            name="ck_order_sales_cost_snapshot_cost",
        ),
    )
    op.create_index("ix_paypal_checkout_verified", "paypal_checkouts", ["verified_at", "order_id"])


def downgrade():
    # Preflight every earlier history guard before SQLite DDL can partially run.
    for table, label in (
        ("refund_requests", "refund"),
        ("paypal_checkouts", "payment"),
        ("order_sales_cost_snapshots", "sales cost snapshot"),
        ("product_sales_cost_bases", "selected cost basis"),
        ("supplier_comparisons", "sourcing"),
        ("supplier_quotes", "sourcing"),
        ("sourcing_inputs", "sourcing"),
    ):
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"Cannot downgrade sales reporting while {label} records exist.")
    op.drop_index("ix_paypal_checkout_verified", table_name="paypal_checkouts")
    op.drop_table("order_sales_cost_snapshots")
    op.drop_table("product_sales_cost_bases")
