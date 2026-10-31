"""Disclosure drafts and seller-approved public Passport snapshots."""

import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "passport_drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("content", sa.JSON(), nullable=False),
        sa.CheckConstraint("revision >= 1", name="ck_passport_drafts_revision"),
    )
    op.create_index("ix_passport_drafts_product_id", "passport_drafts", ["product_id"])
    op.create_table(
        "passport_publications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("draft_id", sa.String(36), sa.ForeignKey("passport_drafts.id"), nullable=False),
        sa.Column(
            "approved_by_account_id", sa.String(36), sa.ForeignKey("accounts.id"), nullable=False
        ),
        sa.Column("draft_revision", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.UniqueConstraint("draft_id", "draft_revision", name="uq_passport_draft_revision"),
        sa.CheckConstraint("draft_revision >= 1", name="ck_passport_publications_revision"),
        sa.CheckConstraint(
            "state IN ('published', 'withdrawn', 'superseded')",
            name="ck_passport_publications_state",
        ),
    )
    op.create_index("ix_passport_publications_product_id", "passport_publications", ["product_id"])
    op.create_index("ix_passport_publications_draft_id", "passport_publications", ["draft_id"])
    op.create_index(
        "uq_passport_active_product",
        "passport_publications",
        ["product_id"],
        unique=True,
        sqlite_where=sa.text("state = 'published'"),
    )


def downgrade():
    op.drop_table("passport_publications")
    op.drop_table("passport_drafts")
