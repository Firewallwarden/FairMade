"""Private supplier profiles, immutable metadata history and reported experiences."""

import sqlalchemy as sa
from alembic import op

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "supplier_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("archived", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "name_key", name="uq_supplier_profile_name"),
        sa.CheckConstraint("revision >= 1", name="ck_supplier_profile_revision"),
        sa.CheckConstraint("archived IN (0, 1)", name="ck_supplier_profile_archived"),
    )
    op.create_index(
        "ix_supplier_profiles_account_created",
        "supplier_profiles",
        ["account_id", "created_at", "id"],
    )
    op.create_table(
        "supplier_profile_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            "supplier_id", sa.String(36), sa.ForeignKey("supplier_profiles.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("before", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "request_id", name="uq_supplier_profile_event_request"),
        sa.UniqueConstraint("supplier_id", "revision", name="uq_supplier_profile_event_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_supplier_profile_event_revision"),
    )
    op.create_table(
        "supplier_experiences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "supplier_id", sa.String(36), sa.ForeignKey("supplier_profiles.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("supplier_revision", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("promised_on", sa.Date(), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=True),
        sa.Column(
            "source_quote_id", sa.String(36), sa.ForeignKey("supplier_quotes.id"), nullable=True
        ),
        sa.Column(
            "corrects_experience_id",
            sa.String(36),
            sa.ForeignKey("supplier_experiences.id"),
            nullable=True,
        ),
        sa.Column("supplier_snapshot", sa.JSON(), nullable=False),
        sa.Column("quote_snapshot", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("supplier_id", "request_id", name="uq_supplier_experience_request"),
        sa.UniqueConstraint("corrects_experience_id", name="uq_supplier_experience_correction"),
        sa.CheckConstraint("supplier_revision >= 1", name="ck_supplier_experience_revision"),
        sa.CheckConstraint(
            "rating IS NULL OR rating BETWEEN 1 AND 5", name="ck_supplier_experience_rating"
        ),
        sa.CheckConstraint(
            "received_on IS NULL OR received_on <= observed_on", name="ck_supplier_experience_dates"
        ),
        sa.CheckConstraint(
            "(source_quote_id IS NULL AND quote_snapshot IS NULL) OR "
            "(source_quote_id IS NOT NULL AND quote_snapshot IS NOT NULL)",
            name="ck_supplier_experience_quote",
        ),
    )
    op.create_index(
        "ix_supplier_experiences_observed",
        "supplier_experiences",
        ["supplier_id", "observed_on", "created_at", "id"],
    )


def downgrade():
    protected = [
        ("supplier_experiences", "supplier experience"),
        ("supplier_profile_events", "supplier profile history"),
        ("supplier_profiles", "supplier profile"),
    ]
    destination = op.get_context().opts.get("destination_rev")
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
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            raise RuntimeError(f"Cannot downgrade supplier records while {label} records exist.")
    if (
        destination not in ("0023", "0022")
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM seller_applications "
                "WHERE status != 'pending' OR revision != 1"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError(
            "Cannot downgrade supplier records while non-pending applications exist."
        )
    op.drop_index("ix_supplier_experiences_observed", table_name="supplier_experiences")
    op.drop_table("supplier_experiences")
    op.drop_table("supplier_profile_events")
    op.drop_index("ix_supplier_profiles_account_created", table_name="supplier_profiles")
    op.drop_table("supplier_profiles")
