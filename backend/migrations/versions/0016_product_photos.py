"""Normalized local photo blobs and current approved listing references."""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_photos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("image_bytes", sa.LargeBinary(), nullable=False),
        sa.CheckConstraint(
            "width BETWEEN 1 AND 2048 AND height BETWEEN 1 AND 2048", name="ck_photo_dimensions"
        ),
        sa.CheckConstraint(
            "byte_count BETWEEN 1 AND 4194304 AND length(image_bytes) = byte_count",
            name="ck_photo_size",
        ),
        sa.CheckConstraint("length(sha256) = 64", name="ck_photo_hash"),
    )
    op.create_index(
        "ix_photo_product_created", "product_photos", ["product_id", "created_at", "id"]
    )
    op.create_table(
        "listing_photos",
        sa.Column(
            "listing_id", sa.String(36), sa.ForeignKey("marketplace_listings.id"), primary_key=True
        ),
        sa.Column("photo_id", sa.String(36), sa.ForeignKey("product_photos.id"), primary_key=True),
    )
    op.create_index("ix_listing_photo_public", "listing_photos", ["photo_id", "listing_id"])


def downgrade():
    for table, label in (
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
            raise RuntimeError(f"Cannot downgrade photos while {label} records exist.")
    op.drop_table("listing_photos")
    op.drop_table("product_photos")
