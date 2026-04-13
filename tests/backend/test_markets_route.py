"""Integration tests for /api/markets endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client():
    """Create a test client against the real FastAPI app with SQLite in-memory DB."""
    import os

    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("POLYGOD_ADMIN_TOKEN", "test-admin-token-abcdef")
    os.environ.setdefault("INTERNAL_API_KEY", "test-internal-key-abcdef")

    from src.backend.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client):
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "god-tier"


@pytest.mark.asyncio
async def test_root_endpoint_returns_200(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "POLYGOD" in data["name"]


@pytest.mark.asyncio
async def test_top50_requires_no_auth(client):
    """Market list endpoint is public — should return 200 even with no auth."""
    response = await client.get("/api/markets/top50")
    # 200 (markets loaded) or 200 with empty list — both are valid on a fresh test DB
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_scan_niches_requires_api_key(client):
    """scan-niches endpoint requires X-API-Key header."""
    response = await client.post("/api/scan-niches")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_polygod_run_requires_admin_token(client):
    """polygod/run requires Bearer token."""
    response = await client.post("/polygod/run", params={"market_id": "test"})
    assert response.status_code in (401, 403)
