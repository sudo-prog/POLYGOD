"""Tests for SQLAlchemy models."""

import pytest
from datetime import datetime


def test_market_to_dict_has_required_keys():
    from src.backend.db_models import Market

    m = Market(
        id="test-id",
        slug="test-slug",
        title="Test Market",
        volume_24h=1000.0,
        volume_7d=7000.0,
        liquidity=500.0,
        yes_percentage=65.0,
        is_active=True,
    )
    d = m.to_dict()
    for key in ("id", "slug", "title", "volume_24h", "volume_7d", "yes_percentage"):
        assert key in d, f"Missing key: {key}"


def test_trade_to_dict_computes_value_usd():
    from src.backend.db_models import Trade

    t = Trade(
        fill_id="fill-abc-123",
        market_id="market-xyz",
        size=500.0,
        price=0.72,
        side="buy",
    )
    d = t.to_dict()
    assert d["value_usd"] == round(500.0 * 0.72, 2)
    assert d["fill_id"] == "fill-abc-123"
    assert d["side"] == "buy"


def test_trade_has_fill_id_field():
    from src.backend.db_models import Trade
    import sqlalchemy as sa

    cols = {c.name for c in Trade.__table__.columns}
    assert "fill_id" in cols
    # fill_id must be unique
    fill_id_col = Trade.__table__.c["fill_id"]
    assert fill_id_col.unique


def test_app_state_to_dict_not_required():
    """AppState has no to_dict — just confirm it instantiates cleanly."""
    from src.backend.db_models import AppState

    a = AppState(key="polygod_mode", value="0")
    assert a.key == "polygod_mode"
    assert a.value == "0"
