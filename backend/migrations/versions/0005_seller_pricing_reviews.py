"""Immutable seller pricing reviews assembled from explicitly selected evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "seller_pricing_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("reviewed_on", sa.Date(), nullable=False),
        sa.Column("review_version", sa.String(100), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_seller_pricing_reviews_basis",
        ),
    )
    op.create_index(
        "ix_seller_pricing_reviews_product_id", "seller_pricing_reviews", ["product_id"]
    )


def downgrade():
    op.drop_table("seller_pricing_reviews")
