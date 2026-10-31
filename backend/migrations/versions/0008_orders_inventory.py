"""Sellable inventory, immutable unpaid order snapshots and expiring holds."""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sellable_inventory",
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("selling_unit", sa.String(200), nullable=False),
        sa.Column("on_hand", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "on_hand >= 0 AND on_hand <= 1000000", name="ck_sellable_inventory_quantity"
        ),
        sa.CheckConstraint("revision >= 1", name="ck_sellable_inventory_revision"),
    )
    op.create_table(
        "orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("buyer_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("seller_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("subtotal_minor", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.UniqueConstraint("buyer_account_id", "idempotency_key", name="uq_order_buyer_key"),
        sa.CheckConstraint("status IN ('pending_payment', 'cancelled')", name="ck_orders_status"),
        sa.CheckConstraint(
            "subtotal_minor > 0 AND subtotal_minor <= 100000000000",
            name="ck_orders_subtotal",
        ),
        sa.CheckConstraint("expires_at > created_at", name="ck_orders_deadline"),
        sa.CheckConstraint(
            "buyer_account_id != seller_account_id", name="ck_orders_different_accounts"
        ),
    )
    op.create_index("ix_order_buyer_created", "orders", ["buyer_account_id", "created_at"])
    op.create_index("ix_order_seller_created", "orders", ["seller_account_id", "created_at"])
    op.create_index("ix_order_reservations", "orders", ["status", "expires_at"])
    op.create_table(
        "order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column(
            "listing_id", sa.String(36), sa.ForeignKey("marketplace_listings.id"), nullable=False
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price_minor", sa.Integer(), nullable=False),
        sa.Column("subtotal_minor", sa.Integer(), nullable=False),
        sa.UniqueConstraint("order_id", "listing_id", name="uq_order_line_listing"),
        sa.CheckConstraint("quantity >= 1 AND quantity <= 10000", name="ck_order_line_quantity"),
        sa.CheckConstraint("unit_price_minor > 0", name="ck_order_line_price"),
        sa.CheckConstraint(
            "subtotal_minor = unit_price_minor * quantity", name="ck_order_line_subtotal"
        ),
    )
    op.create_index("ix_order_line_stock", "order_lines", ["product_id", "order_id"])


def downgrade():
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("sellable_inventory")
