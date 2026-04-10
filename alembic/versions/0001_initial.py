"""create initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-09

This is the baseline migration that creates all tables from scratch.
It is equivalent to what SQLAlchemy Base.metadata.create_all() produced,
but expressed as Alembic DDL so future schema changes can be tracked and
rolled back safely.

If you are migrating from an existing database that was created with
create_all(), run:
    uv run alembic stamp 0001_initial
to mark this migration as already applied without re-running it.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── markets ───────────────────────────────────────────────────────────────
    op.create_table(
        "markets",
        sa.Column("id", sa.String(255), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(500), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("volume_24h", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("volume_7d", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("liquidity", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("yes_percentage", sa.Float, nullable=False, server_default="50.0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("end_date", sa.DateTime, nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("clob_token_ids", sa.Text, nullable=True),
        sa.Column("last_updated", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_markets_volume_7d", "markets", ["volume_7d"])
    op.create_index("idx_markets_is_active", "markets", ["is_active"])
    op.create_index("idx_markets_slug", "markets", ["slug"])

    # ── price_history ─────────────────────────────────────────────────────────
    op.create_table(
        "price_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("market_id", sa.String(255), nullable=False, index=True),
        sa.Column("yes_percentage", sa.Float, nullable=False),
        sa.Column("volume", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("timestamp", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        "idx_price_history_market_time", "price_history", ["market_id", "timestamp"]
    )

    # ── news_articles ─────────────────────────────────────────────────────────
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("market_id", sa.String(255), nullable=False),
        sa.Column("url_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("source", sa.String(255), nullable=True),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("sentiment_score", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_news_market_id", "news_articles", ["market_id"])
    op.create_index("idx_news_published_at", "news_articles", ["published_at"])
    op.create_index(
        "idx_news_market_published", "news_articles", ["market_id", "published_at"]
    )

    # ── app_state ─────────────────────────────────────────────────────────────
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── llm_providers ─────────────────────────────────────────────────────────
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("base_url", sa.String(500), nullable=True),
        sa.Column("api_key_encrypted", sa.String(1000), nullable=True),
        sa.Column("models_json", sa.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("uptime_24h", sa.String(20), nullable=False, server_default="100%"),
        sa.Column("avg_speed", sa.Integer, nullable=True),
        sa.Column("tokens_today", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    # ── agent_configs ─────────────────────────────────────────────────────────
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("agent_name", sa.String(100), unique=True, nullable=False),
        sa.Column("provider_id", sa.Integer, nullable=True),
        sa.Column("model_name", sa.String(200), nullable=True),
        sa.Column("overrides_json", sa.JSON, nullable=True),
    )

    # ── usage_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "usage_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime, nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("agent_name", sa.String(100), nullable=True),
        sa.Column("market_id", sa.String(255), nullable=True),
    )
    op.create_index("idx_usage_logs_timestamp", "usage_logs", ["timestamp"])
    op.create_index("idx_usage_logs_provider", "usage_logs", ["provider"])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_table("usage_logs")
    op.drop_table("agent_configs")
    op.drop_table("llm_providers")
    op.drop_table("app_state")
    op.drop_table("news_articles")
    op.drop_table("price_history")
    op.drop_table("markets")
