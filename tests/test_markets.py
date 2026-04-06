import pytest, respx
from httpx import AsyncClient, Response
from src.backend.main import app


@pytest.mark.asyncio
async def test_top_markets_returns_list():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/markets/top50")
        assert r.status_code == 200
        data = r.json()
        assert "markets" in data
        assert isinstance(data["markets"], list)


async def test_market_history_timeframes():
    for tf in ["24H", "7D", "1M", "ALL"]:
        async with AsyncClient(app=app, base_url="http://test") as client:
            r = await client.get(f"/api/markets/test-market/history?timeframe={tf}")
            # 404 acceptable if market not in DB, 500 is not
            assert r.status_code != 500


async def test_health_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "god-tier"
