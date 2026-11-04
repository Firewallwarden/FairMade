"""Private supplier quotes, input requirements and immutable comparison history."""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sourcing_inputs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("rule_revision", sa.Integer(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("rule_revision >= 0", name="ck_sourcing_inputs_revision"),
    )
    op.create_index(
        "ix_sourcing_input_product_created", "sourcing_inputs", ["product_id", "created_at", "id"]
    )
    op.create_table(
        "supplier_quotes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "sourcing_input_id", sa.String(36), sa.ForeignKey("sourcing_inputs.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.CheckConstraint("basis = 'seller_reported_unverified'", name="ck_supplier_quotes_basis"),
    )
    op.create_index(
        "ix_supplier_quote_input_created",
        "supplier_quotes",
        ["sourcing_input_id", "created_at", "id"],
    )
    op.create_table(
        "supplier_comparisons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "sourcing_input_id", sa.String(36), sa.ForeignKey("sourcing_inputs.id"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("rule_revision", sa.Integer(), nullable=False),
        sa.Column("comparison_version", sa.String(100), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("sourcing_input_snapshot", sa.JSON(), nullable=False),
        sa.Column("product_snapshot", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "basis = 'seller_reported_unverified'", name="ck_supplier_comparisons_basis"
        ),
        sa.CheckConstraint("rule_revision >= 0", name="ck_supplier_comparisons_revision"),
    )
    op.create_index(
        "ix_supplier_comparison_input_created",
        "supplier_comparisons",
        ["sourcing_input_id", "created_at", "id"],
    )


def downgrade():
    # Fail before SQLite DDL rather than partially deleting immutable evidence.
    for table in ("supplier_comparisons", "supplier_quotes", "sourcing_inputs"):
        count = op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        if count:
            raise RuntimeError(
                "Cannot downgrade supplier comparisons while sourcing records exist."
            )
    # Earlier revisions protect financial history. Fail before our SQLite DDL
    # too, so a wider downgrade cannot leave a partially removed newer schema.
    for table, label in (("refund_requests", "refund"), ("paypal_checkouts", "payment")):
        count = op.get_bind().execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
        if count:
            raise RuntimeError(f"Cannot downgrade supplier support while {label} records exist.")
    op.drop_table("supplier_comparisons")
    op.drop_table("supplier_quotes")
    op.drop_table("sourcing_inputs")
