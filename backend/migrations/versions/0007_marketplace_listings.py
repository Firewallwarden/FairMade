"""Private listing drafts and approved searchable catalog snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "marketplace_listings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("published_revision", sa.Integer(), nullable=True),
        sa.Column(
            "published_publication_id",
            sa.String(36),
            sa.ForeignKey("passport_publications.id"),
            nullable=True,
        ),
        sa.Column(
            "approved_by_account_id",
            sa.String(36),
            sa.ForeignKey("accounts.id"),
            nullable=True,
        ),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=True),
        sa.Column("public_payload", sa.JSON(), nullable=True),
        sa.Column("product_type", sa.String(20), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("location_key", sa.String(200), nullable=True),
        sa.Column("price_minor", sa.Integer(), nullable=True),
        sa.UniqueConstraint("product_id"),
        sa.CheckConstraint("revision >= 1", name="ck_marketplace_listings_revision"),
        sa.CheckConstraint(
            "state IN ('draft', 'active', 'inactive')",
            name="ck_marketplace_listings_state",
        ),
        sa.CheckConstraint("price_minor IS NULL OR price_minor > 0", name="ck_listing_price_minor"),
        sa.CheckConstraint(
            "state != 'active' OR (published_revision IS NOT NULL "
            "AND published_publication_id IS NOT NULL AND approved_by_account_id IS NOT NULL "
            "AND published_at IS NOT NULL AND public_payload IS NOT NULL "
            "AND payload_hash IS NOT NULL AND price_minor IS NOT NULL)",
            name="ck_marketplace_listings_approved",
        ),
    )
    op.create_index(
        "ix_listing_browse",
        "marketplace_listings",
        ["state", "product_type", "published_at"],
    )
    op.create_index(
        "ix_listing_location",
        "marketplace_listings",
        ["state", "location_key"],
    )


def downgrade():
    op.drop_table("marketplace_listings")
