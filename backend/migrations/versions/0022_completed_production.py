"""Immutable completed batches/periods and explicit linear corrections."""

import sqlalchemy as sa
from alembic import op

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "production_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(17), nullable=False),
        sa.Column("started_on", sa.Date(), nullable=False),
        sa.Column("completed_on", sa.Date(), nullable=False),
        sa.Column("selling_unit", sa.String(200), nullable=False),
        sa.Column("total_units", sa.Integer(), nullable=False),
        sa.Column("sellable_units", sa.Integer(), nullable=False),
        sa.Column(
            "corrects_record_id",
            sa.String(36),
            sa.ForeignKey("production_records.id"),
            nullable=True,
        ),
        sa.Column("product_snapshot", sa.JSON(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("product_id", "request_id", name="uq_production_record_request"),
        sa.UniqueConstraint("corrects_record_id", name="uq_production_record_correction"),
        sa.CheckConstraint(
            "kind IN ('batch', 'production_period')", name="ck_production_record_kind"
        ),
        sa.CheckConstraint(
            "total_units BETWEEN 0 AND 1000000 AND sellable_units BETWEEN 0 AND total_units",
            name="ck_production_record_output",
        ),
        sa.CheckConstraint("started_on <= completed_on", name="ck_production_record_dates"),
    )
    op.create_index(
        "ix_production_record_product_completed",
        "production_records",
        ["product_id", "completed_on", "created_at", "id"],
    )


def downgrade():
    # Earlier protected data must block before any SQLite DDL in wider rollbacks.
    for table, label in (
        ("production_records", "production"),
        ("material_movements", "material movement"),
        ("materials", "material"),
        ("recipe_costings", "recipe costing"),
        ("product_recipes", "recipe"),
        ("seller_application_decisions", "seller decision"),
        ("admin_bootstrap_records", "administrator bootstrap"),
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
            raise RuntimeError(f"Cannot downgrade production while {label} records exist.")
    if (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM seller_applications "
                "WHERE status != 'pending' OR revision != 1"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Cannot downgrade production while non-pending applications exist.")
    op.drop_index("ix_production_record_product_completed", table_name="production_records")
    op.drop_table("production_records")
