"""
Tests for Kronos/Chronos integration.
Run with: uv run pytest tests/backend/test_kronos.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import polars as pl


@pytest.mark.asyncio
async def test_enrich_returns_dict_with_forecast_keys():
    """Basic contract test — always returns expected keys even with no HF data."""
    with patch(
        "src.backend.tools.kronos_polydata._stream_hf_batches",
        new_callable=AsyncMock,
        return_value=[],  # simulate empty HF response
    ):
        from src.backend.tools.kronos_polydata import enrich_with_kronos_and_polydata

        result = await enrich_with_kronos_and_polydata(
            market_id="test-market",
            prices=[0.5] * 20,  # minimal live price series
        )
    assert "kronos_forecast" in result
    assert "historical_candles" in result
    assert "data_source" in result


@pytest.mark.asyncio
async def test_enrich_handles_insufficient_data_gracefully():
    """Should not crash when fewer than 10 price points available."""
    with patch(
        "src.backend.tools.kronos_polydata._stream_hf_batches",
        new_callable=AsyncMock,
        return_value=[],
    ):
        from src.backend.tools.kronos_polydata import enrich_with_kronos_and_polydata

        result = await enrich_with_kronos_and_polydata("x", prices=[0.5, 0.6])
    assert result["kronos_forecast"].get("signal") == "insufficient_data"


@pytest.mark.asyncio
async def test_hf_stream_timeout_returns_empty():
    """If HF times out, should return empty list without raising."""
    import asyncio

    with patch(
        "src.backend.tools.kronos_polydata.asyncio.to_thread",
        side_effect=asyncio.TimeoutError,
    ):
        from src.backend.tools.kronos_polydata import _stream_hf_batches

        result = await _stream_hf_batches("any-market", timeout_seconds=1)
    assert result == []


def test_build_candles_from_empty_batches_returns_empty_df():
    """Candle builder must not crash on empty input."""
    from src.backend.tools.kronos_polydata import _build_candles_from_batches

    result = _build_candles_from_batches([], "any-market")
    assert isinstance(result, pl.DataFrame)
    assert len(result) == 0


def test_build_candles_yes_pct_is_valid():
    """yes_pct must be between 0 and 1 — validates the B5 aggregation fix."""
    import pyarrow as pa
    import numpy as np

    # Build a minimal fake Arrow batch that matches HF schema
    n = 100
    batch = pa.table(
        {
            "timestamp": pa.array([i * 60_000 for i in range(n)], type=pa.int64()),
            "market_slug": pa.array(["test-market"] * n),
            "price": pa.array(np.random.uniform(0.3, 0.7, n).tolist()),
            "size": pa.array(np.random.uniform(10, 1000, n).tolist()),
            "outcome": pa.array(["YES" if i % 2 == 0 else "NO" for i in range(n)]),
            "category": pa.array(["politics"] * n),
            "trader": pa.array(["0xabc"] * n),
        }
    )

    from src.backend.tools.kronos_polydata import _build_candles_from_batches

    candles = _build_candles_from_batches([batch.to_batches()[0]], "test-market", timeframe="1m")

    if not candles.is_empty():
        assert candles["yes_pct"].min() >= 0.0
        assert candles["yes_pct"].max() <= 1.0
