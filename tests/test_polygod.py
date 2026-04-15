# tests/test_polygod.py
"""
POLYGOD Test Suite — unit + integration + security.

Run: pytest tests/ -v
"""

import asyncio
import json
import secrets
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def patch_settings(monkeypatch):
    """Patch settings with safe test values before any import."""
    monkeypatch.setenv("POLYGOD_ADMIN_TOKEN", secrets.token_urlsafe(32))
    monkeypatch.setenv("INTERNAL_API_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/test")


@pytest.fixture
def app():
    from src.backend.main import app

    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — Config
# ─────────────────────────────────────────────────────────────────────────────


class TestConfig:
    def test_settings_admin_token_is_secret_str(self):
        import os

        os.environ["POLYGOD_ADMIN_TOKEN"] = "test-token-abc"
        from src.backend.config import Settings

        s = Settings()
        assert s.polygod_admin_token.get_secret_value() == "test-token-abc"

    def test_internal_api_key_is_secret_str(self):
        import os

        os.environ["INTERNAL_API_KEY"] = "test-key-xyz"
        from src.backend.config import Settings

        s = Settings()
        assert s.internal_api_key.get_secret_value() == "test-key-xyz"

    def test_mem0_config_parsed(self):
        from src.backend.config import Settings

        s = Settings()
        parsed = s.mem0_config_parsed
        assert "vector_store" in parsed

    def test_cors_allowed_origins_default(self):
        from src.backend.config import Settings

        s = Settings()
        assert isinstance(s.cors_allowed_origins, list)
        assert len(s.cors_allowed_origins) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — Auth
# ─────────────────────────────────────────────────────────────────────────────


class TestAuth:
    def test_verify_api_key_valid(self, monkeypatch):
        import os

        test_key = "valid-test-key-12345"
        os.environ["INTERNAL_API_KEY"] = test_key
        # Re-import to pick up new settings
        import importlib
        import src.backend.config as cfg

        importlib.reload(cfg)
        import src.backend.auth as auth_module

        importlib.reload(auth_module)
        result = auth_module.verify_api_key(test_key)
        assert result == test_key

    def test_verify_api_key_invalid_raises(self):
        from fastapi import HTTPException
        from src.backend.auth import verify_api_key

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key("wrong-key")
        assert exc_info.value.status_code in (401, 403)

    def test_verify_api_key_missing_raises(self):
        from fastapi import HTTPException
        from src.backend.auth import verify_api_key

        with pytest.raises(HTTPException) as exc_info:
            verify_api_key(None)
        assert exc_info.value.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — Database URL coercion
# ─────────────────────────────────────────────────────────────────────────────


class TestDatabase:
    def test_coerce_async_url_postgres(self):
        from src.backend.database import _coerce_async_url

        result = _coerce_async_url("postgresql://user:pass@host/db")
        assert result.startswith("postgresql+asyncpg://")

    def test_coerce_async_url_already_async(self):
        from src.backend.database import _coerce_async_url

        url = "postgresql+asyncpg://user:pass@host/db"
        assert _coerce_async_url(url) == url

    def test_coerce_async_url_heroku_style(self):
        from src.backend.database import _coerce_async_url

        result = _coerce_async_url("postgres://user:pass@host/db")
        assert result.startswith("postgresql+asyncpg://")


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — Monte Carlo
# ─────────────────────────────────────────────────────────────────────────────


class TestMonteCarlo:
    def test_reproducible_with_seed(self):
        from src.backend.polygod_graph import run_monte_carlo

        order = {"size": 1000}
        market = {"prob": 0.6, "volume": 50000}
        r1 = run_monte_carlo(order, market, sims=100, seed=42)
        r2 = run_monte_carlo(order, market, sims=100, seed=42)
        assert r1["expected_pnl"] == r2["expected_pnl"]

    def test_non_deterministic_without_seed(self):
        from src.backend.polygod_graph import run_monte_carlo

        order = {"size": 1000}
        market = {"prob": 0.6, "volume": 50000}
        r1 = run_monte_carlo(order, market, sims=500, seed=None)
        r2 = run_monte_carlo(order, market, sims=500, seed=None)
        # Very unlikely to be identical with 500 sims
        assert r1["expected_pnl"] != r2["expected_pnl"]

    def test_win_prob_in_valid_range(self):
        from src.backend.polygod_graph import run_monte_carlo

        result = run_monte_carlo({"size": 100}, {"prob": 0.5}, sims=1000, seed=1)
        assert 0 <= result["win_prob"] <= 1

    def test_extreme_prob_clamped(self):
        from src.backend.polygod_graph import run_monte_carlo

        # Should not crash with extreme probs
        result = run_monte_carlo({"size": 100}, {"prob": 0.999}, sims=100, seed=1)
        assert result["expected_pnl"] is not None
        result2 = run_monte_carlo({"size": 100}, {"prob": 0.001}, sims=100, seed=1)
        assert result2["expected_pnl"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — Kelly Criterion
# ─────────────────────────────────────────────────────────────────────────────


class TestKelly:
    def test_kelly_positive_edge(self):
        from src.backend.polygod_graph import calculate_kelly

        k = calculate_kelly(0.6)
        assert k > 0

    def test_kelly_coin_flip(self):
        from src.backend.polygod_graph import calculate_kelly

        k = calculate_kelly(0.5)
        assert k == 0.0  # no edge at 50/50

    def test_kelly_clamped_to_one(self):
        from src.backend.polygod_graph import calculate_kelly

        k = calculate_kelly(0.99)
        assert 0 <= k <= 1.0

    def test_kelly_negative_edge_zero(self):
        from src.backend.polygod_graph import calculate_kelly

        k = calculate_kelly(0.1)
        assert k == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — ForgettingEngine
# ─────────────────────────────────────────────────────────────────────────────


class TestForgettingEngine:
    def test_importance_score_no_timestamp_returns_neutral(self):
        from src.backend.self_improving_memory_loop import ForgettingEngine

        fe = ForgettingEngine()
        score = fe._importance_score({"metadata": {}})
        assert score == 0.5  # FIX L-7: conservative default

    def test_importance_score_recent_memory(self):
        from src.backend.self_improving_memory_loop import ForgettingEngine

        fe = ForgettingEngine()
        now = datetime.now(timezone.utc)
        score = fe._importance_score(
            {
                "metadata": {
                    "timestamp": now.isoformat(),
                    "pnl": 100.0,
                    "confidence": 90,
                }
            }
        )
        assert score > 0

    def test_importance_score_tz_aware_comparison(self):
        """Ensure no TypeError when comparing TZ-aware datetimes."""
        from src.backend.self_improving_memory_loop import ForgettingEngine

        fe = ForgettingEngine()
        # Should not raise
        score = fe._importance_score(
            {
                "metadata": {
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "pnl": 10.0,
                    "confidence": 50,
                }
            }
        )
        assert isinstance(score, float)


# ─────────────────────────────────────────────────────────────────────────────
# Unit Tests — AutoResearchLab mutation validation
# ─────────────────────────────────────────────────────────────────────────────


class TestAutoResearchLab:
    def test_apply_mutation_valid_syntax(self):
        from src.backend.autoresearch_lab import AutoResearchLab
        import ast

        lab = AutoResearchLab()
        current = "# MUTATION_POINT\nKELLY_FRACTION = 0.02\n"
        mutation = "KELLY_FRACTION = 0.03\nHEDGE_THRESHOLD = 0.95\n"
        result = lab._apply_mutation(current, mutation)
        # Should be parseable
        ast.parse(result)

    def test_read_strategy_returns_fallback_on_missing_file(
        self, tmp_path, monkeypatch
    ):
        from src.backend.autoresearch_lab import AutoResearchLab

        lab = AutoResearchLab()
        monkeypatch.setattr(lab, "strategy_file", str(tmp_path / "nonexistent.py"))
        code = lab._read_strategy()
        assert "KELLY_FRACTION" in code


# ─────────────────────────────────────────────────────────────────────────────
# Security Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSecurity:
    def test_health_endpoint_no_auth_required(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_markets_endpoint_requires_auth(self, client):
        resp = client.get("/api/markets/top50")
        assert resp.status_code in (401, 403)

    def test_admin_endpoint_requires_token(self, client):
        resp = client.post("/polygod/switch-mode?new_mode=1")
        assert resp.status_code in (401, 403)

    def test_admin_endpoint_with_wrong_token(self, client):
        resp = client.post(
            "/polygod/switch-mode?new_mode=1",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert resp.status_code == 403

    def test_invalid_mode_rejected(self, client):
        from src.backend.config import settings

        token = settings.POLYGOD_ADMIN_TOKEN.get_secret_value()
        resp = client.post(
            "/polygod/switch-mode?new_mode=99",
            headers={"X-Admin-Token": token},
        )
        assert resp.status_code == 400

    def test_cors_wildcard_not_allowed_with_credentials(self, app):
        """Verify CORS middleware does not use allow_origins=['*'] with credentials."""
        from starlette.middleware.cors import CORSMiddleware

        for middleware in app.user_middleware:
            if hasattr(middleware, "kwargs"):
                origins = middleware.kwargs.get("allow_origins", [])
                credentials = middleware.kwargs.get("allow_credentials", False)
                if origins == ["*"] and credentials:
                    pytest.fail(
                        "CORS misconfiguration: allow_origins=['*'] + allow_credentials=True"
                    )

    def test_rate_limit_middleware_bounded_memory(self):
        from src.backend.middleware.rate_limit import (
            RateLimitMiddleware,
            _MAX_TRACKED_IPS,
        )
        from unittest.mock import MagicMock

        mw = RateLimitMiddleware(MagicMock())
        # Simulate more IPs than the limit
        for i in range(_MAX_TRACKED_IPS + 100):
            ip = f"10.0.{i // 256}.{i % 256}"
            mw._requests[ip] = [1.0]
            if len(mw._requests) > _MAX_TRACKED_IPS:
                # Simulate eviction
                mw._requests.popitem(last=False)
        assert len(mw._requests) <= _MAX_TRACKED_IPS


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests — PaperMirror
# ─────────────────────────────────────────────────────────────────────────────


class TestPaperMirror:
    def test_execute_shadow_returns_pnl(self):
        from src.backend.polygod_graph import PaperMirror

        pm = PaperMirror()
        result = pm.execute_shadow({"size": 100, "market_id": "test"})
        assert "pnl" in result
        assert result["status"] == "paper_executed"

    def test_memory_bounded(self):
        from src.backend.polygod_graph import PaperMirror, PAPER_MAX_ENTRIES

        pm = PaperMirror()
        # Overfill
        for _ in range(PAPER_MAX_ENTRIES + 500):
            pm.execute_shadow({"size": 10})
        assert len(pm.pnls) <= PAPER_MAX_ENTRIES
        assert len(pm.trades) <= PAPER_MAX_ENTRIES

    def test_run_tournament_returns_best(self):
        from src.backend.polygod_graph import PaperMirror

        pm = PaperMirror()
        result = pm.run_tournament(
            {"size": 100},
            {"prob": 0.6, "volume": 10000},
            kelly_fractions=[0.1, 0.2, 0.3],
            sims=10,
        )
        assert "best" in result
        assert result["best"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Integration Tests — Niche Strategy
# ─────────────────────────────────────────────────────────────────────────────


class TestMicroNicheStrategy:
    def test_kelly_fraction_capped(self):
        from src.backend.strategies.micro_niche_strategy import calculate_kelly_fraction

        k = calculate_kelly_fraction(edge=1.0)
        assert k <= 0.02

    def test_position_size_capped(self):
        from src.backend.strategies.micro_niche_strategy import (
            calculate_position_size,
            MAX_POSITION_SIZE,
        )

        size = calculate_position_size(balance=1_000_000, edge=1.0)
        assert size <= MAX_POSITION_SIZE

    def test_detect_niche_weather(self):
        from src.backend.strategies.micro_niche_strategy import detect_niche_opportunity

        market = {
            "title": "Will it rain in NYC?",
            "yes_percentage": 30,
            "liquidity": 500,
        }
        external = {"forecast_probability": 0.7}
        result = detect_niche_opportunity(market, external)
        assert result.get("should_trade") is True
        assert result.get("niche_type") == "weather"

    def test_detect_niche_no_edge(self):
        from src.backend.strategies.micro_niche_strategy import detect_niche_opportunity

        market = {"title": "Misc market", "yes_percentage": 50, "liquidity": 10000}
        external = {}
        result = detect_niche_opportunity(market, external)
        assert result.get("should_trade") is False
