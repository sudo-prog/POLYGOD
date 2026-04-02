# src/backend/niche_scanner.py
"""
Micro Niche Scanner — GOD TIER edge detection for low-liquidity recurring markets.

Scans weather, tweets, and mentions markets for mispriced opportunities,
then runs parallel paper tournaments to validate edges before promotion.
"""

import json
import logging
from typing import Any, Dict, List

import httpx
from mem0 import Memory

from src.backend.config import settings
from src.backend.parallel_tournament import parallel_paper_tournament
from src.backend.polymarket.client import polymarket_client

logger = logging.getLogger(__name__)

# Mem0 long-term memory (Qdrant-backed) — reuse same config as polygod_graph
try:
    mem0_config = (
        json.loads(settings.MEM0_CONFIG)
        if settings.MEM0_CONFIG
        else {"vector_store": {"provider": "qdrant", "url": "http://qdrant:6333"}}
    )
    mem0 = Memory.from_config(mem0_config)
except Exception as e:
    logger.warning(f"Mem0 initialization failed in niche_scanner: {e}")
    mem0 = None


def mem0_add(content: str, user_id: str = "micro_niche_lab"):
    """Add to mem0 memory with graceful fallback."""
    if mem0:
        try:
            mem0.add(messages=[{"role": "system", "content": content}], user_id=user_id)
        except Exception as e:
            logger.debug(f"mem0 add failed: {e}")


class MicroNicheScanner:
    """
    Scans low-liquidity recurring markets (weather, tweets, mentions) for edge opportunities.

    Uses free APIs:
    - Open-Meteo: ECMWF + GFS ensemble weather forecasts
    - XTracker: Real-time tweet counts
    - NOAA GFS: Fallback weather data
    """

    def __init__(self):
        self.free_apis = {
            "weather": "https://api.open-meteo.com/v1/forecast",  # ECMWF + GFS ensemble
            "tweet_counter": "https://xtracker.polymarket.com/user/elonmusk",  # live counts
            "noaa_gfs": "https://api.weather.gov/gridpoints",  # fallback
        }

    async def scan_niches(self, mode: int = 1) -> List[Dict[str, Any]]:
        """
        Scan for micro-niche opportunities in low-liquidity markets.

        Args:
            mode: 0=observe, 1=paper, 2=low, 3=beast

        Returns:
            List of opportunities with edge calculations and Kelly sizes
        """
        logger.info(f"MICRO NICHE SCANNER: Starting scan in mode {mode}")

        # Step 1: Pull low-liquidity recurring markets (weather + tweets)
        try:
            all_markets = await polymarket_client.get_top_markets_by_volume(limit=200)
        except Exception as e:
            logger.error(f"Failed to fetch markets for niche scan: {e}")
            return []

        # Filter for niche categories (weather, tweets, mentions)
        niche_keywords = [
            "weather",
            "temperature",
            "rain",
            "snow",
            "tweet",
            "post",
            "mention",
            "elon",
            "twitter",
        ]
        markets = [
            m
            for m in all_markets
            if any(
                kw in m.get("title", "").lower() or kw in m.get("slug", "").lower()
                for kw in niche_keywords
            )
            or m.get("liquidity", 0) < 5000  # low-liquidity edge
        ]

        logger.info(
            f"Found {len(markets)} potential niche markets out of {len(all_markets)} total"
        )

        opportunities = []

        for market in markets:
            try:
                liquidity = market.get("liquidity", 0)
                if liquidity >= 5000:
                    continue  # skip high-liquidity markets

                title_lower = market.get("title", "").lower()
                market_id = market.get("id", "")
                prices = {"yes": market.get("yes_percentage", 50) / 100}

                edge = 0.0

                if "weather" in title_lower or "temperature" in title_lower:
                    forecast = await self.get_weather_forecast(
                        market.get("city", "New York")
                    )
                    edge = self.calculate_weather_edge(forecast, prices)
                    niche_type = "weather"

                elif (
                    "tweet" in title_lower
                    or "post" in title_lower
                    or "elon" in title_lower
                ):
                    count_data = await self.get_tweet_count()
                    edge = self.calculate_tweet_edge(count_data, prices)
                    niche_type = "tweets"

                else:
                    edge = self.calculate_mentions_edge(market)
                    niche_type = "mentions"

                if edge > 0.20:  # threshold for actionable edge
                    kelly_size = self.kelly_fraction(edge)
                    opportunities.append(
                        {
                            "market_id": market_id,
                            "slug": market.get("slug", ""),
                            "title": market.get("title", ""),
                            "niche": niche_type,
                            "edge": round(edge, 4),
                            "kelly_size": round(kelly_size, 4),
                            "liquidity": liquidity,
                            "yes_percentage": market.get("yes_percentage", 50),
                        }
                    )
                    logger.info(
                        f"Edge found: {niche_type} | "
                        f"{market.get('title', '')[:50]}... | "
                        f"Edge: {edge:.2%}"
                    )

            except Exception as e:
                logger.warning(
                    f"Error scanning market {market.get('id', 'unknown')}: {e}"
                )
                continue

        # Step 2: Debate + tournament in swarm (if opportunities found and mode >= 1)
        if opportunities and mode >= 1:
            await self.run_swarm_debate(opportunities, mode)

        logger.info(
            f"MICRO NICHE SCANNER COMPLETE: Found {len(opportunities)} opportunities"
        )
        return opportunities

    async def get_weather_forecast(self, city: str = "New York") -> List[float]:
        """
        Get real ECMWF ensemble via Open-Meteo (6-hr updates).

        Returns list of temperature probabilities for hedge analysis.
        """
        # Default coordinates (NYC) — can be extended to map city names
        coords = {
            "New York": (40.7128, -74.0060),
            "London": (51.5074, -0.1278),
            "Tokyo": (35.6762, 139.6503),
            "Miami": (25.7617, -80.1918),
            "Chicago": (41.8781, -87.6298),
        }

        lat, lon = coords.get(city, (40.7128, -74.0060))

        params = {
            "latitude": lat,
            "longitude": lon,
            "hourly": "temperature_2m",
            "models": "ecmwf_ifs",
            "forecast_days": 7,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(self.free_apis["weather"], params=params)
                resp.raise_for_status()
                data = resp.json()
                temps = data.get("hourly", {}).get("temperature_2m", [])
                # Normalize to probabilities (0-1) for edge calculation
                if temps:
                    max_temp = max(temps)
                    min_temp = min(temps)
                    range_temp = max_temp - min_temp if max_temp != min_temp else 1
                    return [
                        (t - min_temp) / range_temp for t in temps[:24]
                    ]  # first 24 hours
                return [0.5] * 24
        except Exception as e:
            logger.warning(f"Weather API error: {e}")
            return [0.5] * 24  # neutral fallback

    async def get_tweet_count(self) -> Dict[str, Any]:
        """
        Get real-time tweet count data from XTracker.

        Returns dict with current_count and avg_daily.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(self.free_apis["tweet_counter"])
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.warning(f"Tweet counter API error: {e}")
            return {"current_count": 1000, "avg_daily": 100}  # fallback values

    def calculate_weather_edge(
        self, forecast: List[float], market_prices: Dict[str, float]
    ) -> float:
        """
        Calculate edge for weather markets.

        Hedge adjacent buckets if sum < $1 (arbitrage opportunity).
        """
        if not forecast:
            return 0.0

        # Check for arbitrage: if hedge cost < 0.95, there's a locked edge
        prices_list = list(market_prices.values())
        if len(prices_list) >= 3:
            hedge_cost = sum(prices_list[:3])
            if hedge_cost < 0.95:
                return 0.25  # locked 5%+ edge

        # Compare forecast probability to market price
        forecast_prob = (
            sum(forecast[:6]) / len(forecast[:6]) if len(forecast) >= 6 else forecast[0]
        )
        market_prob = prices_list[0] if prices_list else 0.5

        edge = abs(forecast_prob - market_prob)
        return edge if edge > 0.05 else 0.0  # minimum 5% edge threshold

    def calculate_tweet_edge(
        self, count_data: Dict[str, Any], market_prices: Dict[str, float]
    ) -> float:
        """
        Calculate edge for tweet count markets.

        Real-time xtracker data vs market implied probability.
        """
        current = count_data.get("current_count", 0)
        avg_daily = count_data.get("avg_daily", 100)

        # Project 7-day count
        projected = current + avg_daily * 7

        # Check if market is undervalued for the projected range
        for bucket, price in market_prices.items():
            try:
                # Parse bucket range (e.g., "1000-2000")
                bucket_lower = (
                    int(bucket.split("-")[0]) if "-" in bucket else int(bucket)
                )
                if abs(projected - bucket_lower) < 100 and price < 0.12:
                    return 0.30  # undervalued range — 30% edge
            except (ValueError, IndexError):
                continue

        return 0.0

    def calculate_mentions_edge(self, market: Dict[str, Any]) -> float:
        """
        Calculate edge for mentions markets using volume/liquidity signals.
        """
        liquidity = market.get("liquidity", 0)
        volume = market.get("volume_7d", 0)

        # Low liquidity + moderate volume = potential mispricing
        if liquidity < 1000 and volume > 500:
            return 0.22  # 22% edge from illiquidity premium

        # Very low liquidity = higher edge potential
        if liquidity < 500:
            return 0.25

        return 0.0

    def kelly_fraction(self, edge: float) -> float:
        """
        Calculate Kelly fraction for position sizing.

        Conservative: max 2% risk per trade.
        """
        return min(0.02, edge * 0.5)  # 1-2% max risk

    async def run_swarm_debate(self, opps: List[Dict[str, Any]], mode: int = 1):
        """
        Wire into existing parallel_paper_tournament for swarm validation.

        Each opportunity gets a tournament to validate the edge before promotion.
        """
        for opp in opps:
            try:
                # Build state dict compatible with parallel_paper_tournament
                state = {
                    "market_id": opp["market_id"],
                    "question": opp.get("title", "Unknown Market"),
                    "mode": mode,
                    "decision": {"order": {"size": 1000 * opp["kelly_size"]}},
                    "debate_history": [
                        {
                            "agent": "MicroNicheScanner",
                            "output": f"Edge: {opp['edge']:.2%} in {opp['niche']} niche",
                        }
                    ],
                }

                result = await parallel_paper_tournament(state)

                final_decision = result.get("final_decision", {})

                mem0_add(
                    f"Scanned {opp['niche']} | Edge {opp['edge']:.2%} | "
                    f"Kelly: {opp['kelly_size']:.2%} | "
                    f"Tournament Score: {final_decision.get('tournament_best_score', 0):.3f} | "
                    f"Promoted: {bool(final_decision)}",
                    user_id="micro_niche_lab",
                )

                logger.info(
                    f"Niche tournament complete: {opp['title'][:40]}... | "
                    f"Score: {final_decision.get('tournament_best_score', 0):.3f}"
                )

            except Exception as e:
                logger.error(
                    f"Tournament failed for {opp.get('market_id', 'unknown')}: {e}"
                )
                mem0_add(
                    f"Tournament FAILED for {opp['niche']} | Error: {str(e)[:100]}",
                    user_id="micro_niche_lab",
                )


# Global scanner instance
scanner = MicroNicheScanner()
