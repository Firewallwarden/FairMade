"""Buyer-authored immediately published product reviews with historical purchase evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("buyer_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column(
            "listing_id", sa.String(36), sa.ForeignKey("marketplace_listings.id"), nullable=False
        ),
        sa.Column("order_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), nullable=False),
        sa.Column("purchase_capture_id", sa.String(64), nullable=False),
        sa.Column("purchase_verified_at", sa.DateTime(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("buyer_account_id", "product_id", name="uq_review_buyer_product"),
        sa.CheckConstraint("revision >= 1", name="ck_product_review_revision"),
        sa.CheckConstraint("state IN ('published', 'withdrawn')", name="ck_product_review_state"),
        sa.CheckConstraint("rating BETWEEN 1 AND 5", name="ck_product_review_rating"),
        sa.CheckConstraint("length(text) BETWEEN 1 AND 2000", name="ck_product_review_text"),
    )
    op.create_index(
        "ix_review_product_public", "product_reviews", ["product_id", "state", "created_at", "id"]
    )
    op.create_index(
        "ix_review_author_created", "product_reviews", ["buyer_account_id", "created_at", "id"]
    )


def downgrade():
    for table, label in (
        ("product_reviews", "product review"),
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
            raise RuntimeError(f"Cannot downgrade product reviews while {label} records exist.")
    op.drop_table("product_reviews")
