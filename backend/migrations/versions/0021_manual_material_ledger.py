"""Private manual material balances and immutable quantity movements."""

import sqlalchemy as sa
from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "materials",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("unit", sa.String(4), nullable=False),
        sa.Column("on_hand_micros", sa.BigInteger(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "name_key", name="uq_material_account_name"),
        sa.CheckConstraint("revision >= 1", name="ck_material_revision"),
        sa.CheckConstraint("unit IN ('g', 'ml', 'item')", name="ck_material_unit"),
        sa.CheckConstraint(
            "on_hand_micros BETWEEN 0 AND 1000000000000000", name="ck_material_balance"
        ),
        sa.CheckConstraint(
            "unit != 'item' OR on_hand_micros % 1000000 = 0", name="ck_material_whole_items"
        ),
    )
    op.create_index("ix_materials_account_created", "materials", ["account_id", "created_at", "id"])
    op.create_table(
        "material_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("material_id", sa.String(36), sa.ForeignKey("materials.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("material_name", sa.String(200), nullable=False),
        sa.Column("unit", sa.String(4), nullable=False),
        sa.Column("before_micros", sa.BigInteger(), nullable=False),
        sa.Column("after_micros", sa.BigInteger(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("material_id", "request_id", name="uq_material_movement_request"),
        sa.UniqueConstraint("material_id", "revision", name="uq_material_movement_revision"),
        sa.CheckConstraint("revision >= 2", name="ck_material_movement_revision"),
        sa.CheckConstraint(
            "kind IN ('receipt', 'usage', 'waste', 'adjustment')", name="ck_material_movement_kind"
        ),
        sa.CheckConstraint("unit IN ('g', 'ml', 'item')", name="ck_material_movement_unit"),
        sa.CheckConstraint(
            "before_micros BETWEEN 0 AND 1000000000000000 "
            "AND after_micros BETWEEN 0 AND 1000000000000000",
            name="ck_material_movement_balance",
        ),
        sa.CheckConstraint(
            "unit != 'item' OR (before_micros % 1000000 = 0 AND after_micros % 1000000 = 0)",
            name="ck_material_movement_whole_items",
        ),
        sa.CheckConstraint(
            "(kind = 'receipt' AND after_micros > before_micros) OR "
            "(kind IN ('usage', 'waste') AND after_micros < before_micros) OR kind = 'adjustment'",
            name="ck_material_movement_direction",
        ),
    )
    op.create_index(
        "ix_material_movements_material_revision",
        "material_movements",
        ["material_id", "revision", "id"],
    )


def downgrade():
    # Protect wider rollbacks before any SQLite DDL, including earlier guards.
    for table, label in (
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
            raise RuntimeError(f"Cannot downgrade materials while {label} records exist.")
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
        raise RuntimeError("Cannot downgrade materials while non-pending applications exist.")
    op.drop_index("ix_material_movements_material_revision", table_name="material_movements")
    op.drop_table("material_movements")
    op.drop_index("ix_materials_account_created", table_name="materials")
    op.drop_table("materials")
