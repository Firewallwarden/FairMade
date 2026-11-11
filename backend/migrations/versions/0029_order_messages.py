"""Append-only private order messages, with safe retries and indexed cursor history."""

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "order_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("sender_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("sender_role", sa.String(6), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("order_id", "sequence", name="uq_order_message_sequence"),
        sa.UniqueConstraint(
            "order_id", "sender_account_id", "request_id", name="uq_order_message_request"
        ),
        sa.CheckConstraint("sequence BETWEEN 1 AND 1000", name="ck_order_message_sequence"),
        sa.CheckConstraint("sender_role IN ('buyer', 'seller')", name="ck_order_message_role"),
        sa.CheckConstraint("length(text) BETWEEN 1 AND 2000", name="ck_order_message_text"),
    )
    op.create_index(
        "ix_order_message_sender_created", "order_messages", ["sender_account_id", "created_at"]
    )


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT COUNT(*) FROM order_messages")).scalar_one():
        raise RuntimeError("Cannot downgrade while order message history exists.")
    destination = op.get_context().opts.get("destination_rev")
    # Mirror the parent preflight before any nontransactional SQLite DDL.
    if destination != "0028":
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
                if bind.execute(
                    sa.text("SELECT COUNT(*) FROM assistant_conversations")
                ).scalar_one():
                    raise RuntimeError(
                        "Cannot downgrade while assistant conversation history exists."
                    )
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
    op.drop_index("ix_order_message_sender_created", table_name="order_messages")
    op.drop_table("order_messages")
