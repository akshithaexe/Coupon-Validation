"""Seed data

Revision ID: 002
Revises: 001
Create Date: 2024-01-01 00:00:01.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Deterministic UUIDs for easy demo and testing
USER_1_ID = "11111111-1111-1111-1111-111111111111"
USER_2_ID = "22222222-2222-2222-2222-222222222222"
COUPON_ACTIVE_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
COUPON_INACTIVE_ID = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO users (id) VALUES (:id1), (:id2)"
        ).bindparams(id1=USER_1_ID, id2=USER_2_ID)
    )

    op.execute(
        sa.text(
            "INSERT INTO coupons (id, code, discount_percentage, is_active) "
            "VALUES (:id1, :code1, :pct1, :active1), (:id2, :code2, :pct2, :active2)"
        ).bindparams(
            id1=COUPON_ACTIVE_ID,
            code1="WELCOME100",
            pct1=100,
            active1=True,
            id2=COUPON_INACTIVE_ID,
            code2="EXPIRED50",
            pct2=50,
            active2=False,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM coupons WHERE id IN (:id1, :id2)").bindparams(
            id1=COUPON_ACTIVE_ID, id2=COUPON_INACTIVE_ID
        )
    )
    op.execute(
        sa.text("DELETE FROM users WHERE id IN (:id1, :id2)").bindparams(
            id1=USER_1_ID, id2=USER_2_ID
        )
    )
