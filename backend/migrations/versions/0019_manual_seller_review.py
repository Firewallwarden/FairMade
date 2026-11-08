"""Manual seller decisions and first-admin operator audit, without automatic grants."""

import sqlalchemy as sa
from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade():
    # No table references applications before this migration. Rebuild only that
    # small table, preserving IDs, account links, timestamps and pending states.
    with op.batch_alter_table("seller_applications") as batch:
        batch.drop_constraint("ck_seller_applications_status", type_="check")
        batch.alter_column("status", existing_type=sa.String(7), type_=sa.String(8))
        batch.add_column(sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint(
            "ck_seller_applications_status", "status IN ('pending', 'approved', 'denied')"
        )
        batch.create_check_constraint("ck_seller_applications_revision", "revision >= 1")
    op.create_table(
        "seller_application_decisions",
        sa.Column(
            "application_id",
            sa.String(36),
            sa.ForeignKey("seller_applications.id"),
            primary_key=True,
        ),
        sa.Column(
            "decided_by_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("outcome", sa.String(8), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("outcome IN ('approved', 'denied')", name="ck_seller_decision_outcome"),
        sa.CheckConstraint("expected_revision >= 1", name="ck_seller_decision_revision"),
        sa.CheckConstraint("length(reason) BETWEEN 1 AND 2000", name="ck_seller_decision_reason"),
    )
    op.create_table(
        "admin_bootstrap_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_admin_bootstrap_singleton"),
        sa.CheckConstraint("length(reason) BETWEEN 1 AND 2000", name="ck_admin_bootstrap_reason"),
    )


def downgrade():
    for table, label in (
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
            raise RuntimeError(f"Cannot downgrade seller review while {label} records exist.")
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
        raise RuntimeError("Cannot downgrade seller review while non-pending applications exist.")
    op.drop_table("admin_bootstrap_records")
    op.drop_table("seller_application_decisions")
    with op.batch_alter_table("seller_applications") as batch:
        batch.drop_constraint("ck_seller_applications_status", type_="check")
        batch.drop_constraint("ck_seller_applications_revision", type_="check")
        batch.drop_column("revision")
        batch.alter_column("status", existing_type=sa.String(8), type_=sa.String(7))
        batch.create_check_constraint("ck_seller_applications_status", "status = 'pending'")
