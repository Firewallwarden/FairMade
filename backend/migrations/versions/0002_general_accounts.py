"""General accounts, buyer defaults, and pending seller applications."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    # Native SQLite renames update dependent foreign keys without rebuilding or
    # dropping parent tables. Requires SQLite 3.26+ (standard modern Python builds).
    op.rename_table("sellers", "accounts")
    for table in ("sessions", "products"):
        op.drop_index(f"ix_{table}_seller_id", table_name=table)
        op.execute(f"ALTER TABLE {table} RENAME COLUMN seller_id TO account_id")
        op.create_index(f"ix_{table}_account_id", table, ["account_id"])

    op.create_table(
        "account_roles",
        sa.Column("account_id", sa.String(36), sa.ForeignKey("accounts.id"), primary_key=True),
        sa.Column("role", sa.String(6), primary_key=True),
        sa.CheckConstraint("role IN ('buyer', 'seller', 'admin')", name="ck_account_roles_role"),
    )
    op.execute("INSERT INTO account_roles (account_id, role) SELECT id, 'buyer' FROM accounts")
    op.create_table(
        "seller_applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False, unique=True
        ),
        sa.Column("submitted_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(7), nullable=False, server_default="pending"),
        sa.CheckConstraint("status = 'pending'", name="ck_seller_applications_status"),
    )


def downgrade():
    # Downgrading discards new application/role data and restores the old
    # seller-only authorization model, but preserves accounts and their records.
    op.drop_table("seller_applications")
    op.drop_table("account_roles")
    for table in ("sessions", "products"):
        op.drop_index(f"ix_{table}_account_id", table_name=table)
        op.execute(f"ALTER TABLE {table} RENAME COLUMN account_id TO seller_id")
        op.create_index(f"ix_{table}_seller_id", table, ["seller_id"])
    op.rename_table("accounts", "sellers")
