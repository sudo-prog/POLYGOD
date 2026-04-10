"""
tests/backend/conftest.py — Shared fixtures for POLYGOD backend tests.

Stack:
  pytest-asyncio  (async test support)
  httpx           (async test client via ASGITransport)
  respx           (mock external HTTP calls — Polymarket, NewsAPI, CLOB)
  faker           (realistic test data generation)

Run the suite:
  uv run pytest tests/backend -v --cov=src/backend --cov-report=term-missing

Environment:
  Tests use an in-memory SQLite database — no external services required.
  All outbound HTTP (Polymarket API, NewsAPI, CLOB) is intercepted by respx.
"""

import asyncio
import json
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from faker import Faker
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Force test settings before importing anything from the app ────────────────
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("POLYGOD_ADMIN_TOKEN", "test-admin-token-for-ci")
os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key-for-ci")
os.environ.setdefault("ENCRYPTION_KEY", "dGVzdC1lbmNyeXB0aW9uLWtleS0zMi1ieXRlcyE=")
os.environ.setdefault("POLYGOD_MODE", "0")

from src.backend.database import Base, get_db  # noqa: E402 — must follow env setup
from src.backend.main import app                # noqa: E402

fake = Faker()


# ── In-memory database ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create an in-memory SQLite engine for the session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a fresh database session for each test.
    All changes are rolled back after the test to keep tests isolated.
    """
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Yield an HTTPX AsyncClient wired to the FastAPI app.
    The database dependency is overridden to use the test session.
    """
    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


# ── Test data factories ───────────────────────────────────────────────────────

def make_market(
    market_id: str | None = None,
    slug: str | None = None,
    yes_percentage: float = 55.0,
    volume_7d: float = 150_000.0,
    is_active: bool = True,
    clob_token_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Build a realistic market dict for DB insertion or API mocking."""
    mid = market_id or fake.uuid4()
    return {
        "id": mid,
        "slug": slug or fake.slug(),
        "title": fake.sentence(nb_words=8).rstrip(".") + "?",
        "description": fake.paragraph(),
        "volume_24h": volume_7d / 7,
        "volume_7d": volume_7d,
        "liquidity": volume_7d * 0.3,
        "yes_percentage": yes_percentage,
        "is_active": is_active,
        "end_date": None,
        "image_url": None,
        "clob_token_ids": json.dumps(clob_token_ids or [fake.uuid4(), fake.uuid4()]),
    }


def make_gamma_api_market(market: dict) -> dict:
    """Shape a market dict as the Gamma API would return it."""
    yes_price = market["yes_percentage"] / 100
    return {
        "conditionId": market["id"],
        "slug": market["slug"],
        "question": market["title"],
        "description": market.get("description", ""),
        "active": market["is_active"],
        "closed": False,
        "archived": False,
        "volume24hr": market["volume_24h"],
        "volume1wk": market["volume_7d"],
        "liquidityNum": market["liquidity"],
        "outcomePrices": json.dumps([yes_price, 1 - yes_price]),
        "clobTokenIds": market.get("clob_token_ids", "[]"),
        "endDateIso": None,
        "image": "",
        "icon": "",
    }


@pytest_asyncio.fixture
async def seeded_market(db_session: AsyncSession) -> dict[str, Any]:
    """Insert one market into the test DB and return its dict."""
    from src.backend.db_models import Market

    market_data = make_market(
        market_id="test-market-001",
        slug="will-btc-hit-100k",
        yes_percentage=62.5,
        volume_7d=200_000.0,
        clob_token_ids=["token-yes-001", "token-no-001"],
    )
    market = Market(**market_data)
    db_session.add(market)
    await db_session.commit()
    return market_data


# ── Auth helpers ──────────────────────────────────────────────────────────────

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token-for-ci"}
API_KEY_HEADERS = {"X-API-Key": "test-internal-key-for-ci"}
