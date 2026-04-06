import pytest
from httpx import AsyncClient, ASGITransport
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
    """Malicious slugs should not cause crashes or data leaks.
    They may return 404 (market not found) or 422 (validation error)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/markets/{slug}/history")
        # Either 404 (not found) or 422 (validation error) is acceptable
        assert r.status_code in (404, 422), f"Unexpected status {r.status_code} for slug: {slug}"


async def test_valid_slug_accepted():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/markets/valid-slug-123/history")
        # 404 is fine (market not found) — 422 would mean our regex rejected it
        assert r.status_code != 422


async def test_cors_dev_origin():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/health", headers={"Origin": "http://evil.com"})
        assert "http://evil.com" not in r.headers.get("access-control-allow-origin", "")
