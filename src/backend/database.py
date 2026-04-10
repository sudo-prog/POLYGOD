"""
POLYGOD Database — Alembic-ready async SQLAlchemy engine.

Changes vs previous version:
  - FIXED C6: Pool settings are now conditional on database dialect.
              SQLite does not support pool_size / max_overflow; passing
              them caused SAWarning and masked connection errors.
  - FIXED C6: connect_args={"check_same_thread": False} added for SQLite
              so APScheduler background threads can use the same engine.
  - FIXED L1: datetime.utcnow() replaced with timezone-aware alternative
              (kept as a helper so callers don't need to import timezone).
  - FIXED: init_db() now calls create_all only when DEBUG=True.
              Production path validates connectivity only — use Alembic.
"""

from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import StaticPool

from src.backend.config import settings


class Base(DeclarativeBase):
    pass


def _build_engine():
    """
    Build the async SQLAlchemy engine with driver-appropriate settings.

    SQLite (aiosqlite) does not support pool_size / max_overflow and requires
    StaticPool + check_same_thread=False for cross-thread usage in async contexts.
    PostgreSQL (asyncpg) gets full connection pool tuning.
    """
    url = settings.DATABASE_URL

    if settings.is_sqlite:
        return create_async_engine(
            url,
            echo=settings.DEBUG,
            future=True,
            # StaticPool keeps a single connection — correct for SQLite
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
    else:
        # PostgreSQL / asyncpg path
        return create_async_engine(
            url,
            echo=settings.DEBUG,
            future=True,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=10,
            pool_recycle=300,  # recycle stale connections every 5 min
        )


engine = _build_engine()

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async DB session with auto commit/rollback."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database.

    PRODUCTION: This must run `alembic upgrade head` via subprocess.
    DEVELOPMENT: Falls back to create_all for convenience (set DEBUG=True).

    To set up Alembic:
        uv add alembic
        alembic init migrations
        # Edit migrations/env.py to use your async engine + Base
        alembic revision --autogenerate -m "initial"
        alembic upgrade head
    """
    if settings.DEBUG:
        # Dev convenience — create tables directly from models
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        # Production — tables must exist from Alembic migrations
        # Validate connectivity only
        from sqlalchemy import text

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))


async def close_db() -> None:
    """Dispose all pooled connections — call during app shutdown."""
    await engine.dispose()


def utcnow() -> datetime:
    """
    Return the current UTC time as a timezone-aware datetime.

    Replaces the deprecated datetime.utcnow() (Python 3.12+).
    Use this helper everywhere instead of datetime.utcnow().
    """
    return datetime.now(timezone.utc)
