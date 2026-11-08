"""Reusable private recipes and immutable manual costing provenance."""

import sqlalchemy as sa
from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "product_recipes",
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_product_recipe_revision"),
    )
    op.create_table(
        "recipe_costings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "product_id", sa.String(36), sa.ForeignKey("product_recipes.product_id"), nullable=False
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("recipe_revision", sa.Integer(), nullable=False),
        sa.Column(
            "pricing_analysis_id", sa.String(36), sa.ForeignKey("analyses.id"), nullable=False
        ),
        sa.Column("recipe_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("recipe_revision >= 1", name="ck_recipe_costing_revision"),
        sa.UniqueConstraint("product_id", "request_id", name="uq_recipe_costing_request"),
        sa.UniqueConstraint("pricing_analysis_id"),
    )
    op.create_index(
        "ix_recipe_costings_product_created", "recipe_costings", ["product_id", "created_at", "id"]
    )


def downgrade():
    # SQLite DDL is not reliably transactional. Preflight earlier guards too,
    # before dropping anything during a multi-revision downgrade.
    for table, label in (
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
            raise RuntimeError(f"Cannot downgrade recipes while {label} records exist.")
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
        raise RuntimeError("Cannot downgrade recipes while non-pending applications exist.")
    op.drop_index("ix_recipe_costings_product_created", table_name="recipe_costings")
    op.drop_table("recipe_costings")
    op.drop_table("product_recipes")
