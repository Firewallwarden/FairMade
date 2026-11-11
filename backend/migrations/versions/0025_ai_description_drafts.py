"""Private generated description drafts and exact seller review."""

import sqlalchemy as sa
from alembic import op

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "description_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("generated_text", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_snapshot", sa.JSON(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("model", sa.String(40), nullable=False),
        sa.Column("tone", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("approved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "approved_by_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=True
        ),
        sa.UniqueConstraint("product_id", "request_id", name="uq_description_draft_request"),
        sa.CheckConstraint(
            "revision BETWEEN 1 AND 2147483646", name="ck_description_draft_revision"
        ),
        sa.CheckConstraint("state IN ('draft', 'approved')", name="ck_description_draft_state"),
        sa.CheckConstraint(
            "length(description) BETWEEN 1 AND 2000", name="ck_description_draft_text"
        ),
        sa.CheckConstraint(
            "provider = 'ollama_local' AND model = 'qwen3:8b'", name="ck_description_draft_provider"
        ),
        sa.CheckConstraint("tone IN ('plain', 'friendly')", name="ck_description_draft_tone"),
        sa.CheckConstraint(
            "(state = 'draft' AND approved_at IS NULL AND approved_by_account_id IS NULL) OR "
            "(state = 'approved' AND approved_at IS NOT NULL "
            "AND approved_by_account_id IS NOT NULL)",
            name="ck_description_draft_approval",
        ),
    )
    op.create_index(
        "ix_description_draft_product_created",
        "description_drafts",
        ["product_id", "created_at", "id"],
    )


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM description_drafts")).scalar_one():
        raise RuntimeError("Cannot downgrade while AI description draft review history exists.")
    # SQLite DDL is not transactional. Preserve earlier refusal semantics BEFORE
    # dropping this empty table when a wider rollback would be refused downstream.
    destination = op.get_context().opts.get("destination_rev")
    protected = []
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
            raise RuntimeError(f"Cannot downgrade descriptions while {label} records exist.")
    if (
        destination not in ("0024", "0023", "0022")
        and bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM seller_applications "
                "WHERE status != 'pending' OR revision != 1"
            )
        ).scalar_one()
    ):
        raise RuntimeError("Cannot downgrade descriptions while non-pending applications exist.")
    op.drop_index("ix_description_draft_product_created", table_name="description_drafts")
    op.drop_table("description_drafts")
