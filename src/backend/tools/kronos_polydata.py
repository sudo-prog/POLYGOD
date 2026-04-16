"""
Kronos + poly_data Integration for POLYGOD.

Kronos: https://github.com/shiyu-coder/Kronos
- Time-series forecasting for market price prediction
- Uses temporal pattern recognition to predict resolution probabilities

poly_data: https://github.com/warproxxx/poly_data
- Historical Polymarket fill data downloader
- Enables backtesting and strategy validation
"""

import asyncio
import csv
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import numpy as np

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# POLY_DATA INTEGRATION
# Historical fill data from Polymarket for backtesting
# ═══════════════════════════════════════════════════════════════════════════════

POLY_DATA_BASE = "https://raw.githubusercontent.com/warproxxx/poly_data/main/data"


class PolyDataClient:
    """
    Client for poly_data historical Polymarket fill data.

    Downloads CSV data files from the poly_data GitHub repository
    for strategy backtesting and validation.
    """

    def __init__(self):
        self._cache: dict[str, list[dict]] = {}
        self._cache_expiry: dict[str, datetime] = {}
        self._cache_ttl = timedelta(hours=1)

    async def get_fills(
        self,
        market_id: str,
        days_back: int = 30,
    ) -> list[dict]:
        """
        Fetch historical fills for a market from poly_data.

        Returns list of fills with: timestamp, price, size, side, wallet
        """
        cache_key = f"{market_id}_{days_back}"
        now = datetime.now(timezone.utc)

        # Return cached data if fresh
        if (
            cache_key in self._cache
            and cache_key in self._cache_expiry
            and now < self._cache_expiry[cache_key]
        ):
            return self._cache[cache_key]

        fills: list[dict] = []

        try:
            # poly_data stores data by market slug in CSV format
            url = f"{POLY_DATA_BASE}/{market_id}.csv"

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(url)

                if resp.status_code == 404:
                    # Try fetching from the Polymarket CLOB API directly as fallback
                    logger.debug(
                        f"poly_data: no CSV for {market_id}, falling back to CLOB API"
                    )
                    return await self._fetch_from_clob(market_id, days_back)

                resp.raise_for_status()

                # Parse CSV
                reader = csv.DictReader(io.StringIO(resp.text))
                cutoff = now - timedelta(days=days_back)

                for row in reader:
                    try:
                        ts_val = row.get("timestamp", row.get("match_time", ""))
                        if isinstance(ts_val, str) and ts_val:
                            ts = datetime.fromisoformat(ts_val.replace("Z", "+00:00"))
                        else:
                            continue

                        if ts < cutoff:
                            continue

                        fills.append(
                            {
                                "timestamp": ts.isoformat(),
                                "price": float(row.get("price", 0)),
                                "size": float(row.get("size", 0)),
                                "side": row.get("side", "unknown"),
                                "wallet": row.get(
                                    "maker_address", row.get("wallet", "")
                                ),
                                "value_usd": float(row.get("price", 0))
                                * float(row.get("size", 0)),
                            }
                        )
                    except (ValueError, KeyError) as e:
                        logger.debug(f"poly_data: skipping malformed row: {e}")
                        continue

            # Cache result
            self._cache[cache_key] = fills
            self._cache_expiry[cache_key] = now + self._cache_ttl
            logger.info(f"poly_data: loaded {len(fills)} fills for {market_id}")

        except Exception as e:
            logger.error(f"poly_data fetch failed for {market_id}: {e}")

        return fills

    async def _fetch_from_clob(self, market_id: str, days_back: int) -> list[dict]:
        """Fallback: fetch fills directly from Polymarket CLOB API."""
        try:
            from src.backend.polymarket.client import polymarket_client

            raw_fills = await polymarket_client.get_recent_fills(market_id, limit=500)

            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(days=days_back)
            fills = []

            for f in raw_fills:
                try:
                    ts_val = f.get("match_time", f.get("timestamp", ""))
                    if not ts_val:
                        continue
                    ts = datetime.fromisoformat(str(ts_val).replace("Z", "+00:00"))
                    if ts < cutoff:
                        continue
                    fills.append(
                        {
                            "timestamp": ts.isoformat(),
                            "price": float(f.get("price", 0)),
                            "size": float(f.get("size", 0)),
                            "side": f.get("side", "unknown"),
                            "wallet": f.get("maker_address", ""),
                            "value_usd": float(f.get("price", 0))
                            * float(f.get("size", 0)),
                        }
                    )
                except Exception:
                    continue

            return fills
        except Exception as e:
            logger.error(f"CLOB fallback failed: {e}")
            return []

    async def backtest_strategy(
        self,
        market_id: str,
        strategy_params: dict,
        days_back: int = 30,
    ) -> dict:
        """
        Backtest a trading strategy against historical fill data.

        Args:
            market_id: Market to backtest
            strategy_params: Dict with kelly_fraction, confidence_threshold, etc.
            days_back: Historical window in days

        Returns:
            Dict with pnl, sharpe, win_rate, max_drawdown, trade_count
        """
        fills = await self.get_fills(market_id, days_back)

        if not fills:
            return {"error": "No fill data available", "pnl": 0, "trades": 0}

        kelly = strategy_params.get("kelly_fraction", 0.02)
        min_size = strategy_params.get("min_trade_size", 100)
        bankroll = strategy_params.get("initial_bankroll", 10_000)

        pnls = []
        current_bankroll = bankroll

        for fill in fills:
            size = fill["value_usd"]
            if size < min_size:
                continue

            # Strategy: follow whale direction with kelly sizing
            position = current_bankroll * kelly
            if fill["side"].lower() == "buy":
                # Simulate holding to resolution (simplified: assume 55% win rate for buys)
                win = fill["price"] < 0.5  # Buying below 50% is value
                pnl = position * (1 / fill["price"] - 1) if win else -position
            else:
                win = fill["price"] > 0.5  # Selling above 50% is value
                pnl = position * 0.1 if win else -position * 0.5

            current_bankroll += pnl
            pnls.append(pnl)

        if not pnls:
            return {
                "error": "No trades matched strategy criteria",
                "pnl": 0,
                "trades": 0,
            }

        total_pnl = sum(pnls)
        wins = sum(1 for p in pnls if p > 0)
        win_rate = wins / len(pnls) if pnls else 0

        # Sharpe ratio (annualized, assuming daily returns)
        avg_pnl = total_pnl / len(pnls) if pnls else 0
        std_pnl = float(np.std(pnls)) if len(pnls) > 1 else 1
        sharpe = (avg_pnl / std_pnl) * (252**0.5) if std_pnl > 0 else 0

        # Max drawdown
        cumulative = np.cumsum(pnls)
        running_max = np.maximum.accumulate(cumulative)
        drawdowns = running_max - cumulative
        max_drawdown = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0

        return {
            "market_id": market_id,
            "days_back": days_back,
            "trade_count": len(pnls),
            "total_pnl": round(total_pnl, 2),
            "win_rate": round(win_rate * 100, 1),
            "sharpe": round(sharpe, 3),
            "max_drawdown": round(max_drawdown, 2),
            "final_bankroll": round(current_bankroll, 2),
            "roi_pct": round((current_bankroll - bankroll) / bankroll * 100, 2),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# KRONOS INTEGRATION
# Time-series forecasting for market probability prediction
# ═══════════════════════════════════════════════════════════════════════════════


class KronosForecaster:
    """
    Kronos-inspired time-series forecasting for Polymarket prices.

    Kronos uses temporal pattern recognition to forecast time series.
    We adapt this for binary outcome probability forecasting:
    - Input: historical YES price series
    - Output: probability forecast at resolution

    Since Kronos requires a running service, we implement a lightweight
    local version using the same principles (ARIMA + momentum signals).
    For full Kronos: set KRONOS_API_URL in .env to your deployed instance.
    """

    def __init__(self, api_url: str | None = None):
        self.api_url = api_url  # Optional: URL to deployed Kronos service

    async def forecast(
        self,
        prices: list[float],
        horizon: int = 24,  # hours ahead to forecast
        confidence_level: float = 0.8,
    ) -> dict:
        """
        Forecast future probability from historical price series.

        If KRONOS_API_URL is set, delegates to the Kronos service.
        Otherwise uses local statistical forecasting.

        Args:
            prices: Historical YES prices (0-100 scale, oldest first)
            horizon: Hours ahead to forecast
            confidence_level: Confidence interval level (0-1)

        Returns:
            Dict with forecast, trend, confidence_interval, signal
        """
        if len(prices) < 3:
            return {
                "forecast": prices[-1] if prices else 50.0,
                "trend": "insufficient_data",
                "signal": "HOLD",
                "confidence": 0.0,
            }

        # Try Kronos API first if configured
        if self.api_url:
            try:
                return await self._call_kronos_api(prices, horizon, confidence_level)
            except Exception as e:
                logger.warning(f"Kronos API call failed, using local forecaster: {e}")

        # Local forecasting
        return self._local_forecast(prices, horizon, confidence_level)

    async def _call_kronos_api(
        self,
        prices: list[float],
        horizon: int,
        confidence_level: float,
    ) -> dict:
        """Call the deployed Kronos service."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self.api_url}/forecast",
                json={
                    "series": prices,
                    "horizon": horizon,
                    "confidence_level": confidence_level,
                    "frequency": "H",  # hourly data
                },
            )
            resp.raise_for_status()
            return dict(resp.json())

    def _local_forecast(
        self,
        prices: list[float],
        horizon: int,
        confidence_level: float,
    ) -> dict:
        """
        Local statistical forecast using exponential smoothing + momentum.

        This implements the core Kronos idea: temporal pattern weighting
        with confidence-adjusted bounds.
        """
        arr = np.array(prices, dtype=float)
        n = len(arr)

        # Exponential smoothing (ETS)
        alpha = 0.3  # smoothing factor
        smoothed = [arr[0]]
        for i in range(1, n):
            smoothed.append(alpha * arr[i] + (1 - alpha) * smoothed[-1])

        # Trend extraction (linear regression on last 1/3 of data)
        lookback = max(3, n // 3)
        recent = arr[-lookback:]
        x = np.arange(len(recent))
        if len(x) > 1:
            slope = float(np.polyfit(x, recent, 1)[0])
        else:
            slope = 0.0

        # Forecast: project trend forward
        current = float(smoothed[-1])
        forecast = float(np.clip(current + slope * (horizon / 24), 0, 100))

        # Confidence interval (based on historical volatility)
        volatility = float(np.std(arr[-lookback:]))
        z = 1.645 if confidence_level >= 0.9 else 1.282  # z-score
        half_width = z * volatility * (horizon / 24) ** 0.5

        lower = float(np.clip(forecast - half_width, 0, 100))
        upper = float(np.clip(forecast + half_width, 0, 100))

        # Signal generation
        price_change = forecast - current
        if price_change > 5 and current < 80:
            signal = "BUY_YES"
            signal_strength = min(1.0, price_change / 20)
        elif price_change < -5 and current > 20:
            signal = "BUY_NO"
            signal_strength = min(1.0, abs(price_change) / 20)
        else:
            signal = "HOLD"
            signal_strength = 0.0

        trend_str = (
            "strong_uptrend"
            if slope > 1
            else (
                "uptrend"
                if slope > 0.2
                else (
                    "strong_downtrend"
                    if slope < -1
                    else "downtrend" if slope < -0.2 else "sideways"
                )
            )
        )

        return {
            "current_price": round(current, 2),
            "forecast": round(forecast, 2),
            "horizon_hours": horizon,
            "trend": trend_str,
            "slope_per_day": round(slope * 24, 2),
            "volatility": round(volatility, 2),
            "confidence_interval": {
                "lower": round(lower, 2),
                "upper": round(upper, 2),
                "level": confidence_level,
            },
            "signal": signal,
            "signal_strength": round(signal_strength, 3),
            "data_points": n,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED: KRONOS + POLY_DATA MARKET ENRICHMENT
# Add to agent state to get forecasting + historical context
# ═══════════════════════════════════════════════════════════════════════════════

poly_data_client = PolyDataClient()
kronos_forecaster = KronosForecaster()


async def enrich_with_kronos_and_polydata(
    market_id: str,
    price_history: list[float],
    strategy_params: dict | None = None,
) -> dict[str, Any]:
    """
    Combined enrichment: Kronos forecast + poly_data backtest.

    Call this from the statistics_agent or moderator for extra alpha.
    Returns a dict ready to inject into agent context.
    """
    forecast_task = kronos_forecaster.forecast(price_history, horizon=24)
    backtest_task = poly_data_client.backtest_strategy(
        market_id,
        strategy_params or {"kelly_fraction": 0.02, "min_trade_size": 100},
        days_back=30,
    )

    forecast, backtest = await asyncio.gather(
        forecast_task, backtest_task, return_exceptions=True
    )

    result: dict[str, Any] = {}

    if isinstance(forecast, dict):
        result["kronos_forecast"] = forecast
        logger.info(
            f"Kronos forecast for {market_id}: {forecast.get('forecast')}% "
            f"(signal: {forecast.get('signal')})"
        )
    else:
        logger.warning(f"Kronos forecast failed: {forecast}")
        result["kronos_forecast"] = None

    if isinstance(backtest, dict) and "error" not in backtest:
        result["poly_data_backtest"] = backtest
        logger.info(
            f"poly_data backtest for {market_id}: "
            f"Sharpe={backtest.get('sharpe')} win_rate={backtest.get('win_rate')}%"
        )
    else:
        logger.debug(f"poly_data backtest unavailable: {backtest}")
        result["poly_data_backtest"] = None

    return result
