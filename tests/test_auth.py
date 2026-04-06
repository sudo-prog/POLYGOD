import pytest
from httpx import AsyncClient, ASGITransport
from src.backend.main import app


@pytest.mark.asyncio
async def test_scan_niches_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/scan-niches?mode=1")
        assert r.status_code == 401


async def test_scan_niches_valid_key():
    # Use the default internal API key from config
    headers = {"X-API-Key": "change-this-before-use"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/scan-niches?mode=0", headers=headers)
        assert r.status_code in (200, 202)


async def test_scan_niches_wrong_key():
    headers = {"X-API-Key": "wrong-key"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/scan-niches?mode=1", headers=headers)
        assert r.status_code == 403


async def test_debug_mode_off():
    """Stack traces must not appear in error responses."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/nonexistent-endpoint-xyz")
        assert "Traceback" not in r.text
        assert "site-packages" not in r.text
