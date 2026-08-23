"""Seed demo users

Revision ID: 003
Revises: 002
Create Date: 2024-01-01 00:00:02.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEMO_USER_IDS = [
    "33333333-3333-3333-3333-333333333333",
    "44444444-4444-4444-4444-444444444444",
    "55555555-5555-5555-5555-555555555555",
    "66666666-6666-6666-6666-666666666666",
    "77777777-7777-7777-7777-777777777777",
]


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO users (id) VALUES "
            "(:id1), (:id2), (:id3), (:id4), (:id5) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            id1=DEMO_USER_IDS[0],
            id2=DEMO_USER_IDS[1],
            id3=DEMO_USER_IDS[2],
            id4=DEMO_USER_IDS[3],
            id5=DEMO_USER_IDS[4],
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM coupon_usages WHERE user_id IN (:id1, :id2, :id3, :id4, :id5)"
        ).bindparams(
            id1=DEMO_USER_IDS[0],
            id2=DEMO_USER_IDS[1],
            id3=DEMO_USER_IDS[2],
            id4=DEMO_USER_IDS[3],
            id5=DEMO_USER_IDS[4],
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM transactions WHERE user_id IN (:id1, :id2, :id3, :id4, :id5)"
        ).bindparams(
            id1=DEMO_USER_IDS[0],
            id2=DEMO_USER_IDS[1],
            id3=DEMO_USER_IDS[2],
            id4=DEMO_USER_IDS[3],
            id5=DEMO_USER_IDS[4],
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM users WHERE id IN (:id1, :id2, :id3, :id4, :id5)"
        ).bindparams(
            id1=DEMO_USER_IDS[0],
            id2=DEMO_USER_IDS[1],
            id3=DEMO_USER_IDS[2],
            id4=DEMO_USER_IDS[3],
            id5=DEMO_USER_IDS[4],
        )
    )
