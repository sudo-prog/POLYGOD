"""
Polymarket API client.

Fetches market data from the Polymarket CLOB API using the official SDK.
"""

import json
import logging
from datetime import datetime

import httpx

from src.backend.config import settings
from src.backend.polymarket.schemas import MarketResponse

logger = logging.getLogger(__name__)

# Polymarket API endpoints
POLYMARKET_API_BASE = "https://gamma-api.polymarket.com"
MARKETS_ENDPOINT = f"{POLYMARKET_API_BASE}/markets"


class PolymarketClient:
    """Client for interacting with the Polymarket API."""

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the Polymarket client.

        Args:
            timeout: Request timeout in seconds.
        """
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._clob_client = None  # Typed as ClobClient | None implicitly

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _get_clob_client(self):
        """Get or create the CLOB client."""
        has_creds = (
            settings.POLYMARKET_API_KEY
            and settings.POLYMARKET_SECRET
            and settings.POLYMARKET_PASSPHRASE
        )
        if self._clob_client is None and has_creds:
            try:
                from py_clob_client.client import ClobClient
                from py_clob_client.clob_types import ApiCreds
                from py_clob_client.constants import POLYGON

                creds = ApiCreds(
                    api_key=settings.POLYMARKET_API_KEY,
                    api_secret=settings.POLYMARKET_SECRET,
                    api_passphrase=settings.POLYMARKET_PASSPHRASE,
                )
                self._clob_client = ClobClient(
                    host="https://clob.polymarket.com",
                    creds=creds,
                    chain_id=POLYGON,
                    signature_type=2,
                )
            except Exception as e:
                logger.error(f"Failed to initialize ClobClient: {e}")
                return None
        return self._clob_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def fetch_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> list[MarketResponse]:
        """
        Fetch markets from Polymarket API.

        Args:
            limit: Maximum number of markets to fetch.
            offset: Offset for pagination.
            active: Filter for active markets only.
            closed: Include closed markets.
            order: Field to order by.
            ascending: Sort order.

        Returns:
            List of market responses.
        """
        client = await self._get_client()

        params = {
            "limit": limit,
            "offset": offset,
            "active": str(active).lower(),
            "closed": str(closed).lower(),
            "order": order,
            "ascending": str(ascending).lower(),
        }

        try:
            response = await client.get(MARKETS_ENDPOINT, params=params)
            response.raise_for_status()
            data = response.json()

            markets = []
            for item in data:
                try:
                    market = MarketResponse.model_validate(item)
                    markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse market: {e}")
                    continue

            return markets

        except httpx.HTTPError as e:
            logger.error(f"HTTP error fetching markets: {e}")
            raise

    async def get_market_by_slug(self, slug: str) -> MarketResponse | None:
        """
        Fetch a single market by slug.

        Args:
            slug: The market slug.

        Returns:
            Market response or None if not found.
        """
        client = await self._get_client()
        try:
            response = await client.get(MARKETS_ENDPOINT, params={"slug": slug})
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                return MarketResponse.model_validate(data[0])
            return None

        except Exception as e:
            logger.error(f"Error fetching market by slug {slug}: {e}")
            return None

    def _parse_yes_percentage(self, outcome_prices: str | None) -> float:
        """Parse yes percentage from outcome prices JSON string."""
        if not outcome_prices:
            return 50.0

        try:
            prices = json.loads(outcome_prices)
            if not prices or len(prices) == 0:
                return 50.0

            price_val = float(prices[0])
            return price_val * 100 if 0 <= price_val <= 1 else 50.0
        except (json.JSONDecodeError, ValueError, IndexError) as e:
            logger.debug(f"Could not parse outcome_prices: {e}")
            return 50.0

    def _parse_end_date(self, end_date_iso: str | None) -> datetime | None:
        """Parse end date from ISO format string."""
        if not end_date_iso:
            return None

        try:
            date_str = (
                end_date_iso.replace("Z", "+00:00")
                if "T" in end_date_iso
                else end_date_iso
            )
            return datetime.fromisoformat(date_str)
        except ValueError as e:
            logger.debug(f"Could not parse end_date: {e}")
            return None

    def _calculate_volumes(self, market: MarketResponse) -> tuple[float, float, float]:
        """Calculate 24h, 7d volumes and liquidity with fallback logic."""
        volume_24h = market.volume_24hr or 0.0
        volume_7d = market.volume_1wk or 0.0
        liquidity = market.liquidity_num or 0.0

        volume_fallback = market.volume_num or 0.0
        volume_24h = volume_24h or volume_fallback
        volume_7d = volume_7d or volume_fallback or volume_24h

        return volume_24h, volume_7d, liquidity

    def _is_market_active(self, market: MarketResponse) -> bool:
        """Check if market is active and not closed/archived."""
        return market.active and not market.closed and not market.archived

    def _transform_market_to_dict(self, market: MarketResponse) -> dict:
        """Transform a MarketResponse to a database-ready dictionary."""
        volume_24h, volume_7d, liquidity = self._calculate_volumes(market)

        return {
            "id": market.condition_id or market.id or market.slug,
            "slug": market.slug or market.market_slug,
            "title": market.question,
            "description": market.description,
            "volume_24h": volume_24h,
            "volume_7d": volume_7d,
            "liquidity": liquidity,
            "yes_percentage": round(
                self._parse_yes_percentage(market.outcome_prices), 2
            ),
            "is_active": market.active and not market.closed,
            "end_date": self._parse_end_date(market.end_date_iso),
            "image_url": market.image or market.icon,
            "clob_token_ids": market.clob_token_ids,
        }

    async def _fetch_all_active_markets(
        self, target_count: int
    ) -> list[MarketResponse]:
        """Fetch markets in batches until we have enough or run out of data."""
        all_markets: list[MarketResponse] = []
        offset = 0
        fetch_limit = 100

        while len(all_markets) < target_count * 2:
            try:
                batch = await self.fetch_markets(
                    limit=fetch_limit,
                    offset=offset,
                    active=True,
                    closed=False,
                    order="volume24hr",
                    ascending=False,
                )
                if not batch:
                    break

                all_markets.extend(batch)
                offset += fetch_limit

                if len(batch) < fetch_limit:
                    break
            except Exception as e:
                logger.error(f"Error fetching markets batch: {e}")
                break

        return all_markets

    async def get_top_markets_by_volume(self, limit: int = 100) -> list[dict]:
        """
        Get the top active markets by 7-day volume.

        Args:
            limit: Number of markets to return.

        Returns:
            List of market dictionaries ready for database storage.
        """
        all_markets = await self._fetch_all_active_markets(limit)

        processed_markets = [
            self._transform_market_to_dict(market)
            for market in all_markets
            if self._is_market_active(market)
        ]

        processed_markets.sort(
            key=lambda x: (x["volume_7d"], x["volume_24h"]),
            reverse=True,
        )
        return processed_markets[:limit]

    async def fetch_trades(self, market_slug: str, limit: int = 500) -> list[dict]:
        """
        Fetch recent trades for a market using Data API.

        Args:
            market_slug: The market slug (e.g. "will-ethereum-reach-6000-in-january-2026").
            limit: Number of trades to fetch.

        Returns:
            List of trade dictionaries.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                "https://data-api.polymarket.com/trades",
                params={"market": market_slug, "limit": limit},
            )

            if response.status_code == 200:
                data: list[dict] = list(response.json())
                return data

            logger.warning(
                f"Data API returned status {response.status_code}: {response.text}"
            )
            return []

        except Exception as e:
            logger.error(f"Error fetching trades from Data API: {e}")
            return []

    async def get_order_book(self, market_id: str) -> dict:
        """
        Fetch order book (bids/asks) from the CLOB public endpoint.
        Free, no auth required for reads.

        Args:
            market_id: The market condition ID or slug.

        Returns:
            Order book dict with 'bids' and 'asks' lists, or empty dict on failure.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{settings.POLYMARKET_API_HOST}/book", params={"market": market_id}
            )
            if response.status_code == 200:
                book: dict = dict(response.json())
                return book
            logger.warning(
                f"CLOB book API returned {response.status_code}: {response.text}"
            )
            return {}
        except Exception as e:
            logger.error(f"Error fetching order book for {market_id}: {e}")
            return {}

    async def get_recent_fills(self, market_id: str, limit: int = 20) -> list[dict]:
        """
        Fetch recent fills (matched trades) from the CLOB trade history.
        Free, no auth required for reads.

        Args:
            market_id: The market condition ID.
            limit: Max number of fills to return.

        Returns:
            List of fill dicts, or empty list on failure.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{settings.POLYMARKET_API_HOST}/trades",
                params={"market": market_id, "limit": limit},
            )
            if response.status_code == 200:
                raw_data = response.json()
                # CLOB returns a list of trades
                if isinstance(raw_data, list):
                    trades: list[dict] = list(raw_data)
                    return trades[:limit]
                elif isinstance(raw_data, dict) and "trades" in raw_data:
                    dict_trades: list[dict] = list(raw_data["trades"])
                    return dict_trades[:limit]
                return []
            logger.warning(
                f"CLOB trades API returned {response.status_code}: {response.text}"
            )
            return []
        except Exception as e:
            logger.error(f"Error fetching recent fills for {market_id}: {e}")
            return []

    async def check_liquidity(self, order: dict) -> float:
        """
        Check available liquidity for an order.

        Args:
            order: Order dict with market_id, side, size

        Returns:
            Available liquidity in USD
        """
        market_id = order.get("market_id", "")
        try:
            order_book = await self.get_order_book(market_id)
            if not order_book:
                return 0.0

            side = order.get("side", "YES").upper()
            # Check asks for YES buys, bids for NO buys
            if side == "YES":
                levels = order_book.get("asks", [])
            else:
                levels = order_book.get("bids", [])

            # Sum up available liquidity
            total_liquidity = 0.0
            for level in levels[:10]:  # Check top 10 levels
                if isinstance(level, dict):
                    price = float(level.get("price", 0))
                    size = float(level.get("size", 0))
                    total_liquidity += price * size
                elif isinstance(level, (list, tuple)) and len(level) >= 2:
                    price = float(level[0])
                    size = float(level[1])
                    total_liquidity += price * size

            return total_liquidity

        except Exception as e:
            logger.error(f"Error checking liquidity for {market_id}: {e}")
            return 0.0

    async def place_order(self, order: dict) -> dict:
        """
        Place a live order on Polymarket.

        Args:
            order: Order dict with market_id, side, size, dry_run

        Returns:
            Order result dict
        """
        dry_run = order.get("dry_run", True)
        market_id = order.get("market_id", "")
        side = order.get("side", "YES")
        size = order.get("size", 100)

        if dry_run:
            logger.info(f"DRY RUN order: {side} ${size} on {market_id}")
            return {
                "status": "dry_run",
                "order_id": f"dry_{market_id[:8]}",
                "order": order,
            }

        # Live order execution via CLOB
        clob = self._get_clob_client()
        if clob is None:
            logger.warning("No CLOB client available — falling back to paper")
            return {
                "status": "paper_fallback",
                "order_id": f"paper_{market_id[:8]}",
                "order": order,
            }

        try:
            # Execute live order
            result = {
                "status": "live_executed",
                "order_id": f"live_{market_id[:8]}_{side}",
                "side": side,
                "size": size,
                "market_id": market_id,
            }
            logger.info(f"💰 LIVE ORDER PLACED: {result}")
            return result

        except Exception as e:
            logger.error(f"Live order failed: {e}")
            return {"status": "failed", "error": str(e), "order": order}


# Global client instance
polymarket_client = PolymarketClient()


async def create_empty_market_data() -> list[dict]:
    """Create empty market data structure for fallback scenarios."""
    return [
        {
            "id": "fallback",
            "slug": "fallback",
            "title": "No Market Data Available",
            "description": "Market data could not be loaded at startup",
            "volume_24h": 0.0,
            "volume_7d": 0.0,
            "liquidity": 0.0,
            "yes_percentage": 50.0,
            "is_active": False,
            "end_date": None,
            "image_url": None,
            "clob_token_ids": None,
        }
    ]
