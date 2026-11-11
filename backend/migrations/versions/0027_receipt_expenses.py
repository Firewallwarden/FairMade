"""Private receipt drafts and immutable reviewed expense snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "receipt_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("ocr_text", sa.Text(), nullable=False),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("extracted", sa.JSON(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("account_id", "request_id", name="uq_receipt_request"),
        sa.UniqueConstraint("account_id", "source_hash", name="uq_receipt_image"),
        sa.CheckConstraint("revision BETWEEN 1 AND 2147483646", name="ck_receipt_revision"),
        sa.CheckConstraint("state IN ('draft', 'approved')", name="ck_receipt_state"),
        sa.CheckConstraint(
            "(state = 'draft' AND approved_at IS NULL) OR "
            "(state = 'approved' AND approved_at IS NOT NULL)",
            name="ck_receipt_approval",
        ),
    )
    op.create_index(
        "ix_receipt_owner_created", "receipt_drafts", ["account_id", "created_at", "id"]
    )
    op.create_table(
        "receipt_expenses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "receipt_id",
            sa.String(36),
            sa.ForeignKey("receipt_drafts.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index(
        "ix_receipt_expense_owner_created",
        "receipt_expenses",
        ["account_id", "created_at", "id"],
    )


def downgrade():
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
                raise RuntimeError(f"Cannot downgrade conversations while {label} records exist.")
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
    op.drop_index("ix_receipt_expense_owner_created", table_name="receipt_expenses")
    op.drop_table("receipt_expenses")
    op.drop_index("ix_receipt_owner_created", table_name="receipt_drafts")
    op.drop_table("receipt_drafts")
