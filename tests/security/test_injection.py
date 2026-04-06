import pytest
from httpx import AsyncClient
from src.backend.main import app

MALICIOUS_SLUGS = [
    "../../../etc/passwd",
    "market; DROP TABLE markets; --",
    "<script>alert(1)</script>",
    "a" * 300,  # too long
    "",  # empty
    "valid-slug-123",  # this one should pass
]


@pytest.mark.asyncio
@pytest.mark.parametrize("slug", MALICIOUS_SLUGS[:-1])
async def test_slug_injection_rejected(slug):
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get(f"/api/markets/{slug}/history")
        assert r.status_code == 422


async def test_valid_slug_accepted():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/markets/valid-slug-123/history")
        # 404 is fine (market not found) — 422 would mean our regex rejected it
        assert r.status_code != 422


async def test_cors_dev_origin():
    async with AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/health", headers={"Origin": "http://evil.com"})
        assert "http://evil.com" not in r.headers.get("access-control-allow-origin", "")
