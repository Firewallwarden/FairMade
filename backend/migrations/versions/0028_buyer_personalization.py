"""Opt-in buyer preferences with revision tombstones and bounded retention."""

import sqlalchemy as sa
from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "buyer_profiles",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Integer(), nullable=False),
        sa.Column("preferences", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("revision BETWEEN 1 AND 2147483646", name="ck_buyer_profile_revision"),
        sa.CheckConstraint(
            "(enabled = 1 AND expires_at IS NOT NULL) OR (enabled = 0 AND expires_at IS NULL)",
            name="ck_buyer_profile_expiry",
        ),
    )
    op.create_index("ix_buyer_profile_expiry", "buyer_profiles", ["expires_at"])


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM buyer_profiles")).scalar_one():
        raise RuntimeError("Cannot downgrade while buyer profile revision history exists.")
    destination = op.get_context().opts.get("destination_rev")
    # Older protected-history preflight, before any nontransactional SQLite DDL.

    if destination != "0027":
        bind = op.get_bind()
        for table in ("receipt_drafts", "receipt_expenses"):
            if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
                raise RuntimeError("Cannot downgrade while receipt or expense history exists.")
        destination = op.get_context().opts.get("destination_rev")
        # Preflight older protected history before any nontransactional SQLite DDL.

        if destination != "0026":
            if bind.execute(sa.text("SELECT COUNT(*) FROM assistant_conversations")).scalar_one():
                raise RuntimeError("Cannot downgrade while assistant conversation history exists.")
            # SQLite DDL cannot roll back a partial downgrade. Preflight the earlier
            # protected history before dropping our empty tables on a wider downgrade.
            protected = []
            if destination != "0025":
                protected.append(("description_drafts", "description draft review history"))
                if destination != "0024":
                    protected += [
                        ("supplier_experiences", "supplier experience"),
                        ("supplier_profile_events", "supplier profile history"),
                        ("supplier_profiles", "supplier profile"),
                    ]
                    if destination != "0023":
                        protected += [
                            ("production_livestock_sources", "livestock production source"),
                            ("livestock_animal_events", "livestock animal history"),
                            ("livestock_group_events", "livestock group history"),
                            ("livestock_animals", "livestock animal"),
                            ("livestock_groups", "livestock group"),
                        ]
                    if destination not in ("0023", "0022"):
                        protected += [
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
                        ]
            for table, label in protected:
                if bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
                    raise RuntimeError(
                        f"Cannot downgrade conversations while {label} records exist."
                    )
            if (
                destination not in ("0025", "0024", "0023", "0022")
                and bind.execute(
                    sa.text(
                        "SELECT COUNT(*) FROM seller_applications "
                        "WHERE status != 'pending' OR revision != 1"
                    )
                ).scalar_one()
            ):
                raise RuntimeError(
                    "Cannot downgrade conversations while non-pending applications exist."
                )
    op.drop_index("ix_buyer_profile_expiry", table_name="buyer_profiles")
    op.drop_table("buyer_profiles")
