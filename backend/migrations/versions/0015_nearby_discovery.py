"""Indexed approved approximate storefront points, without changing prior publications."""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "storefront_discovery_locations",
        sa.Column(
            "storefront_id", sa.String(36), sa.ForeignKey("storefronts.id"), primary_key=True
        ),
        sa.Column("latitude_hundredths", sa.Integer(), nullable=False),
        sa.Column("longitude_hundredths", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "latitude_hundredths BETWEEN -9000 AND 9000", name="ck_discovery_latitude"
        ),
        sa.CheckConstraint(
            "longitude_hundredths BETWEEN -18000 AND 18000", name="ck_discovery_longitude"
        ),
    )
    op.create_index(
        "ix_discovery_area",
        "storefront_discovery_locations",
        ["latitude_hundredths", "longitude_hundredths"],
    )


def downgrade():
    # Stop before any SQLite DDL if a wider downgrade would discard protected history.
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
            raise RuntimeError(f"Cannot downgrade discovery while {label} records exist.")
    op.drop_table("storefront_discovery_locations")
