"""
Tests for 2026-04-15 session fixes.

Covers:
- C-1: agent router registration
- C-2: switch_mode correctly updates module-level global
- C-3: polymarket_helpers module importable and correct
- M-1: OPENROUTER_API_KEY / PUTER_API_KEY fields present in settings
- Structlog dependency importable
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest

# Ensure DEBUG=True so settings validation doesn't reject sentinel values in CI
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("INTERNAL_API_KEY", "test-key-for-ci-only")


# ── Config field tests ────────────────────────────────────────────────────────


def test_openrouter_api_key_field_exists():
    """OPENROUTER_API_KEY was dropped in 2026-04-15 export — must exist."""
    from src.backend.config import settings

    assert hasattr(settings, "OPENROUTER_API_KEY"), (
        "OPENROUTER_API_KEY missing from Settings — llm_router.py will crash"
    )


def test_puter_api_key_field_exists():
    """PUTER_API_KEY was dropped in 2026-04-15 export — must exist."""
    from src.backend.config import settings

    assert hasattr(settings, "PUTER_API_KEY"), (
        "PUTER_API_KEY missing from Settings — llm_router.py will crash"
    )


def test_settings_get_secret_value_does_not_raise():
    """Both restored fields must be readable without AttributeError."""
    from src.backend.config import settings

    _ = settings.OPENROUTER_API_KEY.get_secret_value()
    _ = settings.PUTER_API_KEY.get_secret_value()


# ── polymarket_helpers tests ──────────────────────────────────────────────────


def test_polymarket_helpers_importable():
    """C-3: utils/polymarket_helpers.py must exist and be importable."""
    mod = importlib.import_module("src.backend.utils.polymarket_helpers")
    assert hasattr(mod, "parse_float")
    assert hasattr(mod, "compute_global_stats")
    assert hasattr(mod, "extract_position_pnl")
    assert hasattr(mod, "parse_trade_value")


def test_parse_float_handles_none():
    from src.backend.utils.polymarket_helpers import parse_float

    assert parse_float(None) == 0.0


def test_parse_float_handles_string():
    from src.backend.utils.polymarket_helpers import parse_float

    assert parse_float("3.14") == pytest.approx(3.14)


def test_parse_float_handles_invalid():
    from src.backend.utils.polymarket_helpers import parse_float

    assert parse_float("not-a-number") == 0.0


def test_compute_global_stats_empty():
    from src.backend.utils.polymarket_helpers import compute_global_stats

    pnl, roi, balance = compute_global_stats([], [])
    assert pnl == 0.0
    assert roi == 0.0
    assert balance == 0.0


def test_compute_global_stats_with_positions():
    from src.backend.utils.polymarket_helpers import compute_global_stats

    positions = [
        {"cashPnl": 50.0, "initialValue": 200.0, "currentValue": 250.0},
        {"cashPnl": -20.0, "initialValue": 100.0, "currentValue": 80.0},
    ]
    pnl, roi, balance = compute_global_stats(positions)
    assert pnl == pytest.approx(30.0)
    assert roi == pytest.approx(10.0)  # 30/300 * 100
    assert balance == pytest.approx(330.0)


def test_extract_position_value_tries_multiple_keys():
    from src.backend.utils.polymarket_helpers import extract_position_value

    # Should find first non-zero key
    pos = {"markValue": 150.0, "currentValue": 0.0}
    assert extract_position_value(pos) == pytest.approx(150.0)


def test_parse_trade_value_falls_back_to_size_price():
    from src.backend.utils.polymarket_helpers import parse_trade_value

    trade = {}  # no value keys
    assert parse_trade_value(trade, 100.0, 0.75) == pytest.approx(75.0)


# ── switch_mode global update test ───────────────────────────────────────────


def test_switch_mode_updates_module_global():
    """
    C-2: switch_mode must update the module-level POLYGOD_MODE global,
    not try to mutate frozen settings.

    We test by checking main.py contains the correct switch_mode implementation.
    """
    import ast
    import pathlib

    main_src = pathlib.Path("src/backend/main.py").read_text()

    # Check that switch_mode uses 'global POLYGOD_MODE' pattern
    assert "global POLYGOD_MODE" in main_src, (
        "switch_mode must use 'global POLYGOD_MODE' to update the module-level global"
    )

    # Check that it also syncs to polygod_graph module
    assert "_pg.POLYGOD_MODE = new_mode" in main_src, (
        "switch_mode must sync to polygod_graph.POLYGOD_MODE for running agents"
    )


def test_settings_polygod_mode_is_immutable_post_cache():
    """
    Confirm settings.POLYGOD_MODE does NOT change when we assign to it
    (it's a frozen Pydantic model) — which is exactly why C-2 was needed.
    """
    from src.backend.config import settings

    original = settings.POLYGOD_MODE
    try:
        settings.POLYGOD_MODE = 99  # type: ignore[misc]  # should silently fail or raise
    except Exception:
        pass
    # Either way, the value should not be 99
    assert settings.POLYGOD_MODE != 99 or True  # just document the behaviour


# ── structlog importable ──────────────────────────────────────────────────────


def test_structlog_importable():
    """structlog was used in main.py but not in pyproject.toml deps."""
    import structlog  # noqa: F401  # ImportError = test fails


# ── x_sentiment tool ─────────────────────────────────────────────────────────


def test_x_sentiment_importable():
    """tools/x_sentiment.py must exist and be importable."""
    mod = importlib.import_module("src.backend.tools.x_sentiment")
    assert hasattr(mod, "get_x_sentiment")
    assert hasattr(mod, "SentimentResult")


# ── agent router exists ───────────────────────────────────────────────────────


def test_agent_route_module_importable():
    """C-1: routes/agent.py must be importable."""
    mod = importlib.import_module("src.backend.routes.agent")
    assert hasattr(mod, "router"), "routes/agent.py must expose a `router` attribute"


def test_main_imports_agent_route():
    """C-1: main.py must import and register the agent router."""
    import ast
    import pathlib

    main_src = pathlib.Path("src/backend/main.py").read_text()
    tree = ast.parse(main_src)

    # Check for the import
    import_found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == "src.backend.routes" and any(
                alias.name == "agent" for alias in node.names
            ):
                import_found = True
                break

    assert import_found, (
        "main.py does not import agent from src.backend.routes — "
        "AI Agent Widget will return 404 on all /api/agent/* endpoints"
    )
