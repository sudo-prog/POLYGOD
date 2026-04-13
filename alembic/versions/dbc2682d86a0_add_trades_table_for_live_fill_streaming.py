"""add trades table for live fill streaming

Revision ID: dbc2682d86a0
Revises: 0001_initial
Create Date: 2026-04-13

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "dbc2682d86a0"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── trades ────────────────────────────────────────────────────────────────
    op.create_table(
        "trades",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("fill_id", sa.String(128), unique=True, nullable=False),
        sa.Column("market_id", sa.String(255), nullable=False, index=True),
        sa.Column("size", sa.Float, nullable=False),
        sa.Column("price", sa.Float, nullable=False),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("maker_fee", sa.Float, default=0.0),
        sa.Column("taker_fee", sa.Float, default=0.0),
        sa.Column(
            "timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), index=True
        ),
    )
    op.create_index("idx_trades_market_time", "trades", ["market_id", "timestamp"])
    op.create_index("idx_trades_whale", "trades", ["market_id", "size"])


def downgrade() -> None:
    op.drop_table("trades")
