"""Create tables

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
    )

    op.create_table(
        "coupons",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("discount_percentage", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.CheckConstraint(
            "discount_percentage > 0 AND discount_percentage <= 100",
            name="ck_coupons_discount_range",
        ),
    )

    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("discount_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("final_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("original_amount > 0", name="ck_transactions_original_positive"),
        sa.CheckConstraint("discount_amount >= 0", name="ck_transactions_discount_nonneg"),
        sa.CheckConstraint("final_amount >= 0", name="ck_transactions_final_nonneg"),
    )

    op.create_table(
        "coupon_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("coupon_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("coupons.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("transactions.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("coupon_id", "user_id", name="uq_coupon_usage_coupon_user"),
    )


def downgrade() -> None:
    op.drop_table("coupon_usages")
    op.drop_table("transactions")
    op.drop_table("coupons")
    op.drop_table("users")
