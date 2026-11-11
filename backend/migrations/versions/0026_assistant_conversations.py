"""Owner-bound saved assistant conversations and bounded completed turns."""

import sqlalchemy as sa
from alembic import op

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(6), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "request_id", name="uq_conversation_request"),
        sa.CheckConstraint("role IN ('buyer', 'seller')", name="ck_conversation_role"),
        sa.CheckConstraint("revision BETWEEN 0 AND 40", name="ck_conversation_revision"),
    )
    op.create_index(
        "ix_conversation_owner_updated",
        "assistant_conversations",
        ["account_id", "updated_at", "id"],
    )
    op.create_index("ix_conversation_expiry", "assistant_conversations", ["expires_at"])
    op.create_table(
        "assistant_turns",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("assistant_conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("history_period", sa.JSON(), nullable=True),
        sa.Column("proposed_prices", sa.JSON(), nullable=False),
        sa.Column("context_turns", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("conversation_id", "request_id", name="uq_conversation_turn_request"),
        sa.UniqueConstraint("conversation_id", "revision", name="uq_conversation_turn_revision"),
        sa.CheckConstraint("revision BETWEEN 1 AND 40", name="ck_conversation_turn_revision"),
        sa.CheckConstraint("length(question) BETWEEN 1 AND 2000", name="ck_conversation_question"),
        sa.CheckConstraint("context_turns BETWEEN 0 AND 6", name="ck_conversation_context_turns"),
    )


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM assistant_conversations")).scalar_one():
        raise RuntimeError("Cannot downgrade while assistant conversation history exists.")
    # SQLite DDL cannot roll back a partial downgrade. Preflight the earlier
    # protected history before dropping our empty tables on a wider downgrade.
    destination = op.get_context().opts.get("destination_rev")
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
        raise RuntimeError("Cannot downgrade conversations while non-pending applications exist.")
    op.drop_table("assistant_turns")
    op.drop_index("ix_conversation_expiry", table_name="assistant_conversations")
    op.drop_index("ix_conversation_owner_updated", table_name="assistant_conversations")
    op.drop_table("assistant_conversations")
