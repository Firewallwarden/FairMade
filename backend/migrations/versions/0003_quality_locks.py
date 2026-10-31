"""Current Quality Locks and immutable evaluation history."""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "quality_lock_sets",
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.CheckConstraint("revision >= 0", name="ck_quality_lock_sets_revision"),
    )
    op.create_table(
        "quality_evaluations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("candidate_label", sa.String(200), nullable=False),
        sa.Column("rule_revision", sa.Integer(), nullable=False),
        sa.Column("evaluation_version", sa.String(100), nullable=False),
        sa.Column("basis", sa.String(40), nullable=False),
        sa.Column("rules_snapshot", sa.JSON(), nullable=False),
        sa.Column("claims", sa.JSON(), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.CheckConstraint("rule_revision >= 0", name="ck_quality_evaluations_revision"),
        sa.CheckConstraint(
            "status IN ('passed', 'failed', 'unknown', 'not_evaluated')",
            name="ck_quality_evaluations_status",
        ),
        sa.CheckConstraint(
            "basis = 'seller_reported_unverified'",
            name="ck_quality_evaluations_basis",
        ),
    )
    op.create_index("ix_quality_evaluations_product_id", "quality_evaluations", ["product_id"])


def downgrade():
    op.drop_table("quality_evaluations")
    op.drop_table("quality_lock_sets")
