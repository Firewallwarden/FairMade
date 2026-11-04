"""One seller storefront for the local MVP with independent stable public IDs."""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storefronts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("public_payload", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("location_key", sa.String(200), nullable=True),
        sa.UniqueConstraint("account_id", name="uq_storefront_account"),
        sa.CheckConstraint("revision >= 1", name="ck_storefront_revision"),
        sa.CheckConstraint(
            "state IN ('draft', 'published', 'withdrawn')", name="ck_storefront_state"
        ),
        sa.CheckConstraint(
            "published_revision IS NULL OR "
            "(published_revision >= 1 AND published_revision <= revision)",
            name="ck_storefront_published_revision",
        ),
        sa.CheckConstraint(
            "state != 'published' OR (published_revision IS NOT NULL "
            "AND published_at IS NOT NULL AND payload_hash IS NOT NULL "
            "AND public_payload IS NOT NULL AND search_text IS NOT NULL)",
            name="ck_storefront_published",
        ),
    )
    op.create_index("ix_storefront_browse", "storefronts", ["state", "published_at", "id"])
    op.create_index(
        "ix_storefront_location", "storefronts", ["state", "location_key", "published_at"]
    )


def downgrade():
    for table, label in (
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
            raise RuntimeError(f"Cannot downgrade storefronts while {label} records exist.")
    op.drop_table("storefronts")
