"""Private finished-product price evidence and immutable comparison reports."""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "price_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_price_observations_basis",
        ),
    )
    op.create_index("ix_price_observations_product_id", "price_observations", ["product_id"])
    op.create_table(
        "price_comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("comparison_version", sa.String(100), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("product_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_price_comparisons_basis",
        ),
    )
    op.create_index("ix_price_comparisons_product_id", "price_comparisons", ["product_id"])


def downgrade():
    op.drop_table("price_comparisons")
    op.drop_table("price_observations")
