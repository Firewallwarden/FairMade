"""Private groups, individual animals, append-only profile history and production attribution."""

import sqlalchemy as sa
from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "livestock_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(600), nullable=False),
        sa.Column("species", sa.String(200), nullable=False),
        sa.Column("species_key", sa.String(600), nullable=False),
        sa.Column("breed", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("reported_headcount", sa.Integer(), nullable=True),
        sa.Column("headcount_on", sa.Date(), nullable=True),
        sa.Column("archived", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "name_key", name="uq_livestock_group_name"),
        sa.CheckConstraint("revision >= 1", name="ck_livestock_group_revision"),
        sa.CheckConstraint("archived IN (0, 1)", name="ck_livestock_group_archived"),
        sa.CheckConstraint(
            "(reported_headcount IS NULL AND headcount_on IS NULL) OR "
            "(reported_headcount IS NOT NULL AND reported_headcount BETWEEN 0 AND 1000000 "
            "AND headcount_on IS NOT NULL)",
            name="ck_livestock_group_headcount",
        ),
    )
    op.create_index(
        "ix_livestock_groups_account_created",
        "livestock_groups",
        ["account_id", "created_at", "id"],
    )
    op.create_table(
        "livestock_animals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("identifier", sa.String(200), nullable=False),
        sa.Column("identifier_key", sa.String(600), nullable=False),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("species", sa.String(200), nullable=False),
        sa.Column("species_key", sa.String(600), nullable=False),
        sa.Column("breed", sa.String(200), nullable=True),
        sa.Column("sex", sa.String(7), nullable=False),
        sa.Column("born_on", sa.Date(), nullable=True),
        sa.Column("acquired_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("livestock_groups.id"), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "identifier_key", name="uq_livestock_animal_identifier"),
        sa.CheckConstraint("revision >= 1", name="ck_livestock_animal_revision"),
        sa.CheckConstraint("sex IN ('unknown', 'female', 'male')", name="ck_livestock_animal_sex"),
        sa.CheckConstraint(
            "status IN ('active', 'departed', 'deceased')", name="ck_livestock_animal_status"
        ),
        sa.CheckConstraint(
            "status = 'active' OR group_id IS NULL", name="ck_livestock_animal_membership"
        ),
        sa.CheckConstraint(
            "born_on IS NULL OR acquired_on IS NULL OR born_on <= acquired_on",
            name="ck_livestock_animal_dates",
        ),
    )
    op.create_index(
        "ix_livestock_animals_account_created",
        "livestock_animals",
        ["account_id", "created_at", "id"],
    )
    op.create_index(
        "ix_livestock_animals_group_status", "livestock_animals", ["group_id", "status", "id"]
    )
    create_history("group", "groups")
    create_history("animal", "animals")
    op.create_table(
        "production_livestock_sources",
        sa.Column(
            "record_id", sa.String(36), sa.ForeignKey("production_records.id"), primary_key=True
        ),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("livestock_groups.id"), nullable=True),
        sa.Column("animal_id", sa.String(36), sa.ForeignKey("livestock_animals.id"), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "group_id IS NOT NULL OR animal_id IS NOT NULL", name="ck_production_livestock_target"
        ),
    )
    op.create_index(
        "ix_production_livestock_group", "production_livestock_sources", ["group_id", "record_id"]
    )
    op.create_index(
        "ix_production_livestock_animal", "production_livestock_sources", ["animal_id", "record_id"]
    )


def create_history(kind: str, plural: str):
    op.create_table(
        f"livestock_{kind}_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column(
            f"{kind}_id", sa.String(36), sa.ForeignKey(f"livestock_{plural}.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("occurred_on", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("request", sa.JSON(), nullable=False),
        sa.Column("before", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("after", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "request_id", name=f"uq_livestock_{kind}_event_request"),
        sa.UniqueConstraint(f"{kind}_id", "revision", name=f"uq_livestock_{kind}_event_revision"),
        sa.CheckConstraint("revision >= 1", name=f"ck_livestock_{kind}_event_revision"),
    )


def downgrade():
    protected = [
        "production_livestock_sources",
        "livestock_animal_events",
        "livestock_group_events",
        "livestock_animals",
        "livestock_groups",
    ]
    # Preserve prior releases too before any SQLite DDL during a wider rollback.
    if op.get_context().opts.get("destination_rev") != "0022":
        protected += [
            "production_records",
            "material_movements",
            "materials",
            "recipe_costings",
            "product_recipes",
            "seller_application_decisions",
            "admin_bootstrap_records",
            "product_reviews",
            "pickup_fulfillment_events",
            "product_photos",
            "refund_requests",
            "paypal_checkouts",
            "order_sales_cost_snapshots",
            "product_sales_cost_bases",
            "supplier_comparisons",
            "supplier_quotes",
            "sourcing_inputs",
            "favorites",
            "storefronts",
        ]
    labels = {
        "production_records": "production",
        "material_movements": "material movement",
        "materials": "material",
        "recipe_costings": "recipe costing",
        "product_recipes": "recipe",
        "seller_application_decisions": "seller decision",
        "admin_bootstrap_records": "administrator bootstrap",
        "product_reviews": "product review",
        "pickup_fulfillment_events": "pickup history",
        "product_photos": "photo",
        "refund_requests": "refund",
        "paypal_checkouts": "payment",
        "order_sales_cost_snapshots": "sales cost snapshot",
        "product_sales_cost_bases": "selected cost basis",
        "supplier_comparisons": "sourcing",
        "supplier_quotes": "sourcing",
        "sourcing_inputs": "sourcing",
        "favorites": "favorite",
        "storefronts": "storefront",
    }
    for table in protected:
        if op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one():
            label = labels.get(table, table.replace("_", " "))
            raise RuntimeError(f"Cannot downgrade livestock while {label} records exist.")
    if (
        op.get_context().opts.get("destination_rev") != "0022"
        and op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM seller_applications "
                "WHERE status != 'pending' OR revision != 1"
            )
        )
        .scalar_one()
    ):
        raise RuntimeError("Cannot downgrade livestock while non-pending applications exist.")
    op.drop_index("ix_production_livestock_animal", table_name="production_livestock_sources")
    op.drop_index("ix_production_livestock_group", table_name="production_livestock_sources")
    op.drop_table("production_livestock_sources")
    op.drop_table("livestock_animal_events")
    op.drop_table("livestock_group_events")
    op.drop_index("ix_livestock_animals_group_status", table_name="livestock_animals")
    op.drop_index("ix_livestock_animals_account_created", table_name="livestock_animals")
    op.drop_table("livestock_animals")
    op.drop_index("ix_livestock_groups_account_created", table_name="livestock_groups")
    op.drop_table("livestock_groups")
