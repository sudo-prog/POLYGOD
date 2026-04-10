"""
alembic/env.py — Async SQLAlchemy migration environment for POLYGOD.

Supports both:
  - Online mode  (default): connect to the real database and run migrations
  - Offline mode (--sql):   generate SQL scripts without a live connection

Usage:
  # Apply all pending migrations
  uv run alembic upgrade head

  # Create a new migration (auto-generates diff from models)
  uv run alembic revision --autogenerate -m "describe the change"

  # Downgrade one step
  uv run alembic downgrade -1

  # Show current migration state
  uv run alembic current

  # Show migration history
  uv run alembic history --verbose
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── Import ALL models so Alembic can see the full schema ─────────────────────
# Every SQLAlchemy model must be imported here (or in a module imported here)
# for --autogenerate to detect new tables and columns.
from src.backend.database import Base  # noqa: F401 — Base must be imported first

# Import each model file so their classes register on Base.metadata
import src.backend.db_models          # noqa: F401  Market, PriceHistory, NewsArticle, AppState
import src.backend.models.llm         # noqa: F401  Provider, AgentConfig, UsageLog

# ── Alembic config ────────────────────────────────────────────────────────────
config = context.config

# Configure Python logging from alembic.ini [loggers] section
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Point Alembic at our declarative Base for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """
    Return the database URL.

    Preference order:
      1. POLYGOD_DATABASE_URL env var (set by CI/CD for migration runs)
      2. DATABASE_URL from POLYGOD settings
      3. alembic.ini sqlalchemy.url (fallback)
    """
    import os
    url = os.getenv("POLYGOD_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        return url
    # Lazy import to avoid circular deps at module load
    from src.backend.config import settings
    return settings.DATABASE_URL


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode — generate SQL without a DB connection.

    Useful for reviewing changes or applying them manually via psql / sqlite3.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render ADD COLUMN / DROP COLUMN diffs
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Include schemas for PostgreSQL multi-schema setups
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations online using an async engine.

    We create a throwaway engine here rather than reusing the app engine
    because Alembic needs synchronous connection semantics internally
    (it uses run_sync under the hood).
    """
    url = get_url()

    # Build engine kwargs based on dialect
    is_sqlite = url.startswith("sqlite")
    engine_kwargs: dict = {
        "sqlalchemy.url": url,
    }

    connectable = async_engine_from_config(
        engine_kwargs,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # No pooling in migration runs
        # SQLite needs check_same_thread=False
        **({"connect_args": {"check_same_thread": False}} if is_sqlite else {}),
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations — runs the async loop."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
