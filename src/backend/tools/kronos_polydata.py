"""
POLYGOD Kronos + Polymarket Historical Data Tool
Replaces the original stub in tools/kronos_polydata.py.

Wires:
  - SII-WANGZJ/Polymarket_data (HuggingFace streaming, never full download)
  - Amazon Chronos-T5 foundation model for time-series forecasting
  - Mem0 persistence for long-term agent memory

Called by statistics_agent() in polygod_graph.py via:
    from src.backend.tools.kronos_polydata import enrich_with_kronos_and_polydata
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Literal

import numpy as np
import polars as pl

logger = logging.getLogger(__name__)

# ── Module-level singleton for Chronos model (loaded once per process) ─────────
_chronos_lock = asyncio.Lock()
_chronos_pipeline = None  # type: ignore[assignment]


async def _get_chronos_pipeline():
    """
    Lazy-load the Chronos pipeline once per process, thread-safe.
    Uses asyncio.Lock so concurrent graph nodes don't double-load.
    """
    global _chronos_pipeline
    if _chronos_pipeline is not None:
        return _chronos_pipeline

    async with _chronos_lock:
        if _chronos_pipeline is not None:  # double-check after acquiring lock
            return _chronos_pipeline
        try:
            import torch
            from chronos import ChronosPipeline  # type: ignore[import]

            from src.backend.config import settings

            model_name = settings.KRONOS_MODEL_NAME
            hf_token = settings.HF_TOKEN.get_secret_value() or None

            # CPU-safe device map; swaps to cuda automatically if available
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info("Loading Chronos pipeline: %s on %s", model_name, device)

            _chronos_pipeline = await asyncio.to_thread(
                ChronosPipeline.from_pretrained,
                model_name,
                device_map=device,
                torch_dtype=torch.float32,
                token=hf_token,
            )
            logger.info("Chronos pipeline loaded successfully")
        except Exception as exc:
            logger.warning(
                "Chronos pipeline unavailable: %s — forecasting disabled", exc
            )
            _chronos_pipeline = None

    return _chronos_pipeline


# ── Polars streaming helper ────────────────────────────────────────────────────


def _build_candles_from_batches(
    batches: list,
    market_slug: str,
    timeframe: Literal["1m", "5m", "15m", "1h"] = "5m",
    max_candles: int = 5000,
) -> pl.DataFrame:
    """
    Build OHLCV candles from a list of PyArrow record batches.

    Schema expected from SII-WANGZJ/Polymarket_data/trades.parquet:
      timestamp (int64 unix-ms or utf8 ISO), market_slug (utf8), price (float64),
      size (float64), outcome (utf8: YES/NO), category (utf8), trader (utf8)
    """
    if not batches:
        return pl.DataFrame()

    # CLAUDE FIX B1: Polars cannot scan HF IterableDataset directly.
    # We convert collected Arrow batches to a Polars DataFrame instead.
    import pyarrow as pa

    table = pa.concat_tables([pa.Table.from_batches([b]) for b in batches])
    df = pl.from_arrow(table)

    # Normalise timestamp to Datetime regardless of source format
    if df["timestamp"].dtype == pl.Int64:
        df = df.with_columns(
            pl.col("timestamp").cast(pl.Datetime("ms")).alias("timestamp")
        )
    else:
        df = df.with_columns(
            pl.col("timestamp")
            .str.strptime(pl.Datetime, "%Y-%m-%dT%H:%M:%S%.f")
            .alias("timestamp")
        )

    # Filter to target market
    df = df.filter(pl.col("market_slug").str.contains(market_slug, literal=True))
    if df.is_empty():
        return pl.DataFrame()

    # CLAUDE FIX B5: yes_pct computed correctly with two separate expressions
    yes_vol = (
        pl.when(pl.col("outcome") == "YES")
        .then(pl.col("size").cast(pl.Float64))
        .otherwise(0.0)
    )
    total_vol = pl.col("size").cast(pl.Float64)

    candles = (
        df.with_columns(
            [
                pl.col("timestamp").dt.truncate(timeframe).alias("candle_time"),
                pl.col("price").cast(pl.Float64),
                pl.col("size").cast(pl.Float64).alias("volume"),
            ]
        )
        .group_by(["market_slug", "candle_time"])
        .agg(
            [
                pl.col("price").first().alias("open"),
                pl.col("price").max().alias("high"),
                pl.col("price").min().alias("low"),
                pl.col("price").last().alias("close"),
                pl.col("volume").sum().alias("volume"),
                pl.count("price").alias("trade_count"),
                yes_vol.sum().alias("yes_volume"),
                total_vol.sum().alias("total_volume"),
            ]
        )
        .with_columns(
            (
                pl.col("yes_volume") / pl.col("total_volume").clip(lower_bound=1e-9)
            ).alias("yes_pct")
        )
        .sort("candle_time")
        .tail(max_candles)  # hard cap — never OOM the swarm container
    )
    return candles


async def _stream_hf_batches(
    market_slug: str,
    timeout_seconds: int = 30,
    max_batches: int = 200,  # ~200 * 1000-row batches = 200k rows max per call
) -> list:
    """
    Stream only enough batches from HF to cover the target market.
    Stops early once we have sufficient data, never downloads the full 28 GB.
    """
    from src.backend.config import settings

    hf_token = settings.HF_TOKEN.get_secret_value() or None

    def _sync_stream() -> list:
        from datasets import load_dataset  # type: ignore[import]

        ds = load_dataset(
            "SII-WANGZJ/Polymarket_data",
            data_files="trades.parquet",
            streaming=True,
            split="train",
            token=hf_token,
        )
        ds = ds.with_format("arrow")  # CLAUDE FIX B1: get Arrow batches, not dicts

        collected = []
        found_rows = 0
        for batch in ds:
            collected.append(batch)
            # Early stop: count rows mentioning target slug
            import pyarrow.compute as pc

            if "market_slug" in batch.schema.names:
                mask = pc.match_substring(batch["market_slug"], market_slug)
                found_rows += pc.sum(mask).as_py() or 0

            if len(collected) >= max_batches:
                logger.debug("Kronos: hit max_batches=%d, stopping stream", max_batches)
                break
            if found_rows >= 10_000:
                logger.debug(
                    "Kronos: collected %d target rows, stopping stream early",
                    found_rows,
                )
                break
        return collected

    try:
        batches = await asyncio.wait_for(
            asyncio.to_thread(_sync_stream),
            timeout=timeout_seconds,
        )
        return batches
    except asyncio.TimeoutError:
        logger.warning(
            "Kronos: HF stream timed out after %ds — returning empty", timeout_seconds
        )
        return []
    except Exception as exc:
        logger.warning("Kronos: HF stream failed: %s", exc)
        return []


# ── Main entry point (called by statistics_agent) ─────────────────────────────


async def enrich_with_kronos_and_polydata(
    market_id: str,
    prices: list[float],
    timeframe: Literal["1m", "5m", "15m", "1h"] = "5m",
    horizon: int = 12,
) -> Dict[str, Any]:
    """
    Primary enrichment function — called by statistics_agent() in polygod_graph.py.

    Args:
        market_id:  Polymarket condition ID or slug.
        prices:     Live price series from CLOB (used as fallback if HF stream empty).
        timeframe:  Candle granularity for aggregation.
        horizon:    Number of future candles to forecast.

    Returns:
        Dict compatible with the existing state["market_data"] merge in statistics_agent.
    """
    from src.backend.config import settings

    result: Dict[str, Any] = {
        "kronos_forecast": {},
        "historical_candles": 0,
        "historical_yes_pct_mean": None,
        "historical_volume_7d": None,
        "data_source": "live_only",
    }

    # ── Step 1: stream historical trades ────────────────────────────────────
    try:
        batches = await _stream_hf_batches(
            market_slug=market_id,
            timeout_seconds=settings.KRONOS_STREAM_TIMEOUT,
        )
        candles = _build_candles_from_batches(
            batches,
            market_slug=market_id,
            timeframe=timeframe,
            max_candles=settings.KRONOS_MAX_CANDLES,
        )
    except Exception as exc:
        logger.warning("Kronos: candle build failed: %s", exc)
        candles = pl.DataFrame()

    if not candles.is_empty():
        result["historical_candles"] = len(candles)
        result["historical_yes_pct_mean"] = float(candles["yes_pct"].mean() or 0.0)
        result["historical_volume_7d"] = float(candles["volume"].sum())
        result["data_source"] = "hf_streaming"
        logger.info("Kronos: %d candles aggregated for %s", len(candles), market_id)
    else:
        logger.info(
            "Kronos: no historical data found for %s — using live prices only",
            market_id,
        )

    # ── Step 2: Chronos-T5 forecast ─────────────────────────────────────────
    # Use historical candle close prices if available, else fall back to live feed
    if not candles.is_empty() and len(candles) >= 10:
        price_series = candles["close"].to_list()
    elif len(prices) >= 10:
        price_series = prices
    else:
        # Not enough data for a meaningful forecast
        result["kronos_forecast"] = {
            "signal": "insufficient_data",
            "forecast": None,
            "trend": "unknown",
        }
        return result

    try:
        pipeline = await _get_chronos_pipeline()
        if pipeline is None:
            raise RuntimeError("Chronos pipeline not available")

        import torch

        context = torch.tensor(price_series[-512:], dtype=torch.float32).unsqueeze(0)

        # Run inference off the event loop to avoid blocking
        raw_forecast = await asyncio.to_thread(
            pipeline.predict,
            context,
            horizon,
        )

        # raw_forecast shape: (num_series=1, num_samples, horizon)
        samples = raw_forecast[0].numpy()  # (num_samples, horizon)
        median_forecast = float(np.median(samples, axis=0).mean())
        lower_80 = float(np.percentile(samples, 10, axis=0).mean())
        upper_80 = float(np.percentile(samples, 90, axis=0).mean())

        current = float(price_series[-1])
        delta = median_forecast - current
        signal = (
            "bullish" if delta > 0.02 else "bearish" if delta < -0.02 else "neutral"
        )

        result["kronos_forecast"] = {
            "forecast": round(median_forecast * 100, 2),  # as percentage
            "lower_80": round(lower_80 * 100, 2),
            "upper_80": round(upper_80 * 100, 2),
            "horizon_candles": horizon,
            "timeframe": timeframe,
            "signal": signal,
            "trend": "up" if delta > 0 else "down",
            "delta_pct": round(delta * 100, 2),
        }
        logger.info(
            "Kronos forecast for %s: signal=%s median=%.2f%% (Δ%.2f%%)",
            market_id,
            signal,
            median_forecast * 100,
            delta * 100,
        )

    except Exception as exc:
        logger.warning("Kronos inference failed for %s: %s", market_id, exc)
        result["kronos_forecast"] = {"signal": "model_error", "error": str(exc)}

    # ── Step 3: persist insight to Mem0 ─────────────────────────────────────
    # CLAUDE FIX B7: memory_type is not a valid Mem0 param; use metadata={}
    try:
        from src.backend.polygod_graph import mem0_add

        mem0_add(
            f"Kronos forecast for {market_id}: {result['kronos_forecast']}",
            user_id="polygod",
        )
    except Exception as exc:
        logger.debug("Kronos: mem0 write failed (non-fatal): %s", exc)

    return result


# ── Standalone LangChain tool (for /api/kronos/forecast endpoint) ─────────────

try:
    from langchain_core.tools import (
        tool,
    )

    # CLAUDE FIX B3: use langchain_core not langchain
    from pydantic import BaseModel, Field

    class KronosForecastInput(BaseModel):
        market_slug: str = Field(
            ..., description="Polymarket market slug or condition ID"
        )
        timeframe: Literal["1m", "5m", "15m", "1h"] = Field("5m")
        horizon: int = Field(8, ge=1, le=64)
        category_filter: str | None = Field(None)

    @tool
    async def kronos_forecast_tool(
        market_slug: str, timeframe: str = "5m", horizon: int = 8
    ) -> Dict[str, Any]:
        """LangChain tool: stream Polymarket historical data and run Chronos-T5 forecast."""
        return await enrich_with_kronos_and_polydata(
            market_id=market_slug,
            prices=[],
            timeframe=timeframe,  # type: ignore[arg-type]
            horizon=horizon,
        )

except ImportError:
    kronos_forecast_tool = None  # type: ignore[assignment]

__all__ = [
    "enrich_with_kronos_and_polydata",
    "kronos_forecast_tool",
    "KronosForecastInput",
]
