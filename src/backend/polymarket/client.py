"""
Polymarket API client — public data reads + authenticated CLOB trading.

CLOB Live Order Execution architecture:
  The Polymarket CLOB API requires three things for live trading:
    1. An EVM private key (signs orders on-chain via EIP-712)
    2. API credentials (api_key / secret / passphrase — for HTTP auth)
    3. A token ID (the specific YES or NO token for the market condition)

  Flow for a live order:
    get_token_id_for_market()
      → build_market_order() / build_limit_order()
      → sign_order()  [EIP-712, done inside py_clob_client]
      → post_order()  [HTTP POST to CLOB]
      → poll_order_status() until FILLED / CANCELLED / timeout

  The private key is NEVER stored in the database or logged.
  It lives exclusively in POLYMARKET_PRIVATE_KEY env var.

  New env vars required for live trading (add to .env):
    POLYMARKET_PRIVATE_KEY=0x...   # EVM private key (64 hex chars)
    POLYMARKET_API_KEY=...         # From Polymarket "API keys" page
    POLYMARKET_SECRET=...
    POLYMARKET_PASSPHRASE=...

  For read-only / paper mode none of the above are needed.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Literal

import httpx
from fastapi import WebSocket  # BUG-5 fix: was missing

from src.backend.config import settings
from src.backend.database import async_session_factory  # BUG-2 fix: was missing
from src.backend.db_models import Trade  # BUG-2 fix: was missing
from src.backend.polymarket.schemas import MarketResponse

logger = logging.getLogger(__name__)

POLYMARKET_API_BASE = "https://gamma-api.polymarket.com"
MARKETS_ENDPOINT = f"{POLYMARKET_API_BASE}/markets"
CLOB_HOST = "https://clob.polymarket.com"
POLYGON_CHAIN_ID = 137

# Order-fill poll settings
_ORDER_POLL_INTERVAL_S = 2.0
_ORDER_POLL_TIMEOUT_S = 60.0


# ── Lazy CLOB client helper ───────────────────────────────────────────────────


def _make_clob_client():
    """
    Build a py_clob_client.ClobClient authenticated with the configured creds.

    Returns None if any required credential is missing or py_clob_client is
    not installed.  Callers MUST handle None gracefully.
    """
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
    except ImportError:
        logger.warning("py_clob_client not installed — live trading disabled")
        return None

    pk = (
        settings.POLYMARKET_PRIVATE_KEY.get_secret_value()
        if hasattr(settings, "POLYMARKET_PRIVATE_KEY")
        else ""
    )
    api_key = settings.POLYMARKET_API_KEY.get_secret_value()
    secret = settings.POLYMARKET_SECRET.get_secret_value()
    passphrase = settings.POLYMARKET_PASSPHRASE.get_secret_value()

    if not all([pk, api_key, secret, passphrase]):
        logger.info(
            "CLOB credentials incomplete — live trading disabled. "
            "Set POLYMARKET_PRIVATE_KEY, POLYMARKET_API_KEY, "
            "POLYMARKET_SECRET, POLYMARKET_PASSPHRASE in .env."
        )
        return None

    try:
        creds = ApiCreds(
            api_key=api_key,
            api_secret=secret,
            api_passphrase=passphrase,
        )
        client = ClobClient(
            host=CLOB_HOST,
            key=pk,
            chain_id=POLYGON_CHAIN_ID,
            creds=creds,
            signature_type=2,  # ECDSA poly signature
        )
        logger.info("CLOB client initialised (live trading ENABLED)")
        return client
    except Exception as exc:
        logger.error("Failed to initialise CLOB client: %s", exc)
        return None


# Global active WS connections for live whale alerts
active_connections: list[WebSocket] = []


async def _broadcast_whale_trade(trade_dict: dict) -> None:
    """Broadcast a whale trade to all connected frontend clients."""
    message = {
        "type": "whale_trade",
        "data": trade_dict,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dead: list[WebSocket] = []
    for ws in active_connections[:]:
        try:
            await ws.send_json(message)
        except Exception:
            dead.append(ws)
    for d in dead:
        if d in active_connections:
            active_connections.remove(d)


class PolymarketClient:
    """
    Async client for Polymarket public + authenticated APIs.

    Public reads (market data, order book, fills) require no credentials.
    Live order placement requires POLYMARKET_PRIVATE_KEY + API creds.
    """

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._http: httpx.AsyncClient | None = None
        self._clob = None  # lazy; created on first live-trade attempt
        self._clob_attempted = False  # only try once per process

    # ── HTTP client ───────────────────────────────────────────────────────────

    async def _get_http(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=self.timeout)
        return self._http

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
            self._http = None

    # ── CLOB client (sync, lazy) ──────────────────────────────────────────────

    def _get_clob(self):
        if not self._clob_attempted:
            self._clob_attempted = True
            self._clob = _make_clob_client()
        return self._clob

    # ── Market data reads ─────────────────────────────────────────────────────

    async def fetch_markets(
        self,
        limit: int = 100,
        offset: int = 0,
        active: bool = True,
        closed: bool = False,
        order: str = "volume24hr",
        ascending: bool = False,
    ) -> list[MarketResponse]:
        client = await self._get_http()
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
            markets: list[MarketResponse] = []
            for item in data:
                try:
                    markets.append(MarketResponse.model_validate(item))
                except Exception as exc:
                    logger.warning("Failed to parse market: %s", exc)
            return markets
        except httpx.HTTPError as exc:
            logger.error("HTTP error fetching markets: %s", exc)
            raise

    async def get_market_by_slug(self, slug: str) -> MarketResponse | None:
        client = await self._get_http()
        try:
            response = await client.get(MARKETS_ENDPOINT, params={"slug": slug})
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return MarketResponse.model_validate(data[0])
        except Exception as exc:
            logger.error("Error fetching market by slug %r: %s", slug, exc)
        return None

    def _parse_yes_percentage(self, outcome_prices: str | None) -> float:
        if not outcome_prices:
            return 50.0
        try:
            prices = json.loads(outcome_prices)
            if prices:
                price_val = float(prices[0])
                return price_val * 100 if 0 <= price_val <= 1 else 50.0
        except Exception:
            pass
        return 50.0

    def _parse_end_date(self, end_date_iso: str | None) -> datetime | None:
        if not end_date_iso:
            return None
        try:
            date_str = end_date_iso.replace("Z", "+00:00") if "T" in end_date_iso else end_date_iso
            return datetime.fromisoformat(date_str)
        except ValueError:
            return None

    def _calculate_volumes(self, market: MarketResponse) -> tuple[float, float, float]:
        v24 = market.volume_24hr or 0.0
        v7d = market.volume_1wk or 0.0
        liq = market.liquidity_num or 0.0
        fallback = market.volume_num or 0.0
        v24 = v24 or fallback
        v7d = v7d or fallback or v24
        return v24, v7d, liq

    def _is_market_active(self, market: MarketResponse) -> bool:
        return market.active and not market.closed and not market.archived

    def _transform_market_to_dict(self, market: MarketResponse) -> dict:
        v24, v7d, liq = self._calculate_volumes(market)
        return {
            "id": market.condition_id or market.id or market.slug,
            "slug": market.slug or market.market_slug,
            "title": market.question,
            "description": market.description,
            "volume_24h": v24,
            "volume_7d": v7d,
            "liquidity": liq,
            "yes_percentage": round(self._parse_yes_percentage(market.outcome_prices), 2),
            "is_active": market.active and not market.closed,
            "end_date": self._parse_end_date(market.end_date_iso),
            "image_url": market.image or market.icon,
            "clob_token_ids": market.clob_token_ids,
        }

    async def _fetch_all_active_markets(self, target_count: int) -> list[MarketResponse]:
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
            except Exception as exc:
                logger.error("Error fetching markets batch: %s", exc)
                break
        return all_markets

    async def get_top_markets_by_volume(self, limit: int = 100) -> list[dict]:
        all_markets = await self._fetch_all_active_markets(limit)
        processed = [
            self._transform_market_to_dict(m) for m in all_markets if self._is_market_active(m)
        ]
        processed.sort(key=lambda x: (x["volume_7d"], x["volume_24h"]), reverse=True)
        return processed[:limit]

    async def fetch_trades(self, market_slug: str, limit: int = 500) -> list[dict]:
        try:
            client = await self._get_http()
            response = await client.get(
                "https://data-api.polymarket.com/trades",
                params={"market": market_slug, "limit": limit},
            )
            if response.status_code == 200:
                return list(response.json())
            logger.warning("Data API %d: %s", response.status_code, response.text[:200])
        except Exception as exc:
            logger.error("Error fetching trades: %s", exc)
        return []

    async def get_order_book(self, market_id: str) -> dict:
        try:
            client = await self._get_http()
            response = await client.get(
                f"{settings.POLYMARKET_API_HOST}/book",
                params={"market": market_id},
            )
            if response.status_code == 200:
                return dict(response.json())
            logger.warning("CLOB book API %d for %s", response.status_code, market_id)
        except Exception as exc:
            logger.error("Error fetching order book for %s: %s", market_id, exc)
        return {}

    async def get_recent_fills(self, market_id: str, limit: int = 20) -> list[dict]:
        try:
            client = await self._get_http()
            response = await client.get(
                f"{settings.POLYMARKET_API_HOST}/trades",
                params={"market": market_id, "limit": limit},
            )
            if response.status_code == 200:
                raw = response.json()
                if isinstance(raw, list):
                    return raw[:limit]
                if isinstance(raw, dict) and "trades" in raw:
                    return list(raw["trades"])[:limit]
            logger.warning("CLOB trades API %d for %s", response.status_code, market_id)
        except Exception as exc:
            logger.error("Error fetching fills for %s: %s", market_id, exc)
        return []

    # ── Liquidity check ───────────────────────────────────────────────────────

    async def check_liquidity(self, order: dict) -> float:
        """Sum the top-10 order-book levels to estimate available liquidity."""
        market_id = order.get("market_id", "")
        try:
            book = await self.get_order_book(market_id)
            if not book:
                return 0.0
            side = order.get("side", "YES").upper()
            levels = book.get("asks" if side == "YES" else "bids", [])
            total = 0.0
            for level in levels[:10]:
                if isinstance(level, dict):
                    total += float(level.get("price", 0)) * float(level.get("size", 0))
                elif isinstance(level, (list, tuple)) and len(level) >= 2:
                    total += float(level[0]) * float(level[1])
            return total
        except Exception as exc:
            logger.error("Error checking liquidity for %s: %s", market_id, exc)
            return 0.0

    # ── Token-ID resolution ───────────────────────────────────────────────────

    async def get_token_id_for_market(
        self,
        market_id: str,
        side: Literal["YES", "NO"] = "YES",
    ) -> str | None:
        """
        Resolve the CLOB token ID for YES or NO outcome of a market.

        The token ID is required to build CLOB orders — it identifies exactly
        which binary outcome token to trade, not just the market condition.

        Returns None if the market has no CLOB token IDs configured.
        """
        # Try DB first (fast path)
        try:
            from sqlalchemy import or_, select

            from src.backend.database import async_session_factory
            from src.backend.db_models import Market

            async with async_session_factory() as db:
                result = await db.execute(
                    select(Market.clob_token_ids).where(
                        or_(Market.id == market_id, Market.slug == market_id)
                    )
                )
                row = result.scalar_one_or_none()
                if row:
                    token_ids = json.loads(row)
                    # Convention: index 0 = YES, index 1 = NO
                    idx = 0 if side == "YES" else 1
                    if len(token_ids) > idx:
                        return str(token_ids[idx])
        except Exception as exc:
            logger.warning("DB token-id lookup failed for %s: %s", market_id, exc)

        # Fallback: fetch from Gamma API
        try:
            market = await self.get_market_by_slug(market_id)
            if market and market.clob_token_ids:
                token_ids = json.loads(market.clob_token_ids)
                idx = 0 if side == "YES" else 1
                if len(token_ids) > idx:
                    return str(token_ids[idx])
        except Exception as exc:
            logger.warning("API token-id lookup failed for %s: %s", market_id, exc)

        return None

    # ── Live order placement ──────────────────────────────────────────────────

    async def place_order(self, order: dict) -> dict:
        """
        Place an order on the Polymarket CLOB.

        Order dict fields:
          market_id  (str)  — condition ID or slug
          side       (str)  — "YES" or "NO"
          size       (float)— USD notional to spend
          order_type (str)  — "MARKET" (default) or "LIMIT"
          price      (float)— only required for LIMIT orders (0.0–1.0)
          dry_run    (bool) — if True, skip CLOB post and return a simulation
          token_id   (str)  — optional; looked up automatically if omitted

        Returns a result dict with at minimum:
          status: "dry_run" | "filled" | "open" | "paper_fallback" | "failed"
          order_id: str
          side, size, market_id
        """
        dry_run: bool = order.get("dry_run", True)
        market_id: str = order.get("market_id", "")
        side: str = str(order.get("side", "YES")).upper()
        size: float = float(order.get("size", 100))
        order_type: str = str(order.get("order_type", "MARKET")).upper()
        limit_price: float | None = order.get("price")

        # ── Dry run ──────────────────────────────────────────────────────────
        if dry_run:
            logger.info("DRY RUN order: %s $%.2f on %s", side, size, market_id)
            return {
                "status": "dry_run",
                "order_id": f"dry_{market_id[:8]}",
                "side": side,
                "size": size,
                "market_id": market_id,
            }

        # ── Live path ────────────────────────────────────────────────────────
        clob = self._get_clob()
        if clob is None:
            logger.warning(
                "CLOB credentials not configured — falling back to paper execution. "
                "Set POLYMARKET_PRIVATE_KEY, POLYMARKET_API_KEY, POLYMARKET_SECRET, "
                "POLYMARKET_PASSPHRASE in .env to enable live trading."
            )
            return {
                "status": "paper_fallback",
                "reason": "clob_credentials_missing",
                "order_id": f"paper_{market_id[:8]}",
                "side": side,
                "size": size,
                "market_id": market_id,
            }

        # ── Resolve token ID ──────────────────────────────────────────────────
        token_id: str | None = order.get("token_id") or await self.get_token_id_for_market(
            market_id,
            side,  # type: ignore[arg-type]
        )
        if not token_id:
            logger.error(
                "Cannot place live order: no token_id resolved for market=%s side=%s",
                market_id,
                side,
            )
            return {
                "status": "failed",
                "reason": "token_id_not_found",
                "market_id": market_id,
                "side": side,
            }

        # ── Build and post order ──────────────────────────────────────────────
        try:
            from py_clob_client.clob_types import (
                LimitOrderArgs,
                MarketOrderArgs,
                OrderType,
                TradeParams,
            )
        except ImportError as exc:
            logger.error("py_clob_client import failed: %s", exc)
            return {"status": "failed", "reason": str(exc)}

        try:
            if order_type == "MARKET":
                logger.info(
                    "Placing MARKET order: %s $%.2f on market=%s token=%s",
                    side,
                    size,
                    market_id,
                    token_id,
                )
                order_args = MarketOrderArgs(
                    token_id=token_id,
                    amount=size,  # USD amount to spend
                )
                # create_market_order is synchronous in py_clob_client
                signed_order = await asyncio.to_thread(clob.create_market_order, order_args)
                resp = await asyncio.to_thread(clob.post_order, signed_order, OrderType.FOK)
            else:
                if limit_price is None:
                    raise ValueError("limit_price is required for LIMIT orders")
                if not (0.0 < limit_price < 1.0):
                    raise ValueError(f"limit_price must be between 0 and 1, got {limit_price}")

                logger.info(
                    "Placing LIMIT order: %s $%.2f @ %.4f on market=%s token=%s",
                    side,
                    size,
                    limit_price,
                    market_id,
                    token_id,
                )
                order_args = LimitOrderArgs(  # type: ignore[assignment]
                    token_id=token_id,
                    price=limit_price,
                    size=size,
                    side=side,
                )
                signed_order = await asyncio.to_thread(clob.create_limit_order, order_args)
                resp = await asyncio.to_thread(clob.post_order, signed_order, OrderType.GTC)

            # ── Parse response ────────────────────────────────────────────────
            # py_clob_client returns a dict with keys: orderId, status, ...
            order_id: str = resp.get("orderId", resp.get("order_id", "unknown"))
            status: str = resp.get("status", "unknown").lower()

            logger.info(
                "💰 LIVE ORDER PLACED: id=%s status=%s market=%s side=%s size=%.2f",
                order_id,
                status,
                market_id,
                side,
                size,
            )

            result = {
                "status": status,  # "matched", "live", "delayed" etc.
                "order_id": order_id,
                "side": side,
                "size": size,
                "market_id": market_id,
                "token_id": token_id,
                "raw_response": resp,
                "placed_at": datetime.now(timezone.utc).isoformat(),
            }

            # For MARKET/FOK orders: poll until filled or timeout
            if order_type == "MARKET" and status not in ("matched", "filled"):
                result = await self._poll_order_until_filled(order_id, result)

            return result

        except Exception as exc:
            logger.error(
                "Live order FAILED for market=%s side=%s: %s",
                market_id,
                side,
                exc,
                exc_info=True,
            )
            return {
                "status": "failed",
                "reason": str(exc),
                "side": side,
                "size": size,
                "market_id": market_id,
            }

    # ── Order fill polling ────────────────────────────────────────────────────

    async def _poll_order_until_filled(
        self,
        order_id: str,
        initial_result: dict,
        timeout: float = _ORDER_POLL_TIMEOUT_S,
        interval: float = _ORDER_POLL_INTERVAL_S,
    ) -> dict:
        """
        Poll the CLOB for order status until FILLED, CANCELLED, or timeout.

        Polymarket FOK orders usually fill within a few seconds; this provides
        confirmation rather than just fire-and-forget.
        """
        clob = self._get_clob()
        if clob is None:
            return initial_result

        deadline = asyncio.get_event_loop().time() + timeout
        result = initial_result.copy()

        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(interval)
            try:
                order_resp = await asyncio.to_thread(clob.get_order, order_id)
                status = str(order_resp.get("status", "")).lower()
                result["status"] = status
                result["raw_response"] = order_resp

                if status in ("matched", "filled"):
                    logger.info("Order %s FILLED", order_id)
                    result["filled_at"] = datetime.now(timezone.utc).isoformat()
                    return result

                if status in ("cancelled", "canceled", "unmatched"):
                    logger.warning("Order %s was %s", order_id, status)
                    return result

            except Exception as exc:
                logger.warning("Error polling order %s: %s", order_id, exc)

        logger.warning(
            "Order %s poll timed out after %.0fs — last status: %s",
            order_id,
            timeout,
            result.get("status"),
        )
        return result

    # ── Cancel order ─────────────────────────────────────────────────────────

    async def cancel_order(self, order_id: str) -> dict:
        """
        Cancel an open order by order ID.

        Returns a result dict with status "cancelled" on success.
        Safe to call even if order is already filled (returns a no-op result).
        """
        clob = self._get_clob()
        if clob is None:
            return {"status": "failed", "reason": "clob_credentials_missing"}

        try:
            resp = await asyncio.to_thread(clob.cancel, order_id)
            status = str(resp.get("status", "cancelled")).lower()
            logger.info("Order %s cancel result: %s", order_id, status)
            return {"status": status, "order_id": order_id, "raw_response": resp}
        except Exception as exc:
            logger.error("Failed to cancel order %s: %s", order_id, exc)
            return {"status": "failed", "reason": str(exc), "order_id": order_id}

    # ── Balance check ─────────────────────────────────────────────────────────

    async def get_usdc_balance(self) -> float:
        """
        Return the authenticated wallet's USDC balance on Polygon.

        Used as a pre-trade safety check to prevent over-spending.
        Returns 0.0 if credentials are not configured.
        """
        clob = self._get_clob()
        if clob is None:
            return 0.0
        try:
            balance_resp = await asyncio.to_thread(clob.get_balance)
            return float(balance_resp.get("balance", 0.0))
        except Exception as exc:
            logger.warning("Failed to fetch USDC balance: %s", exc)
            return 0.0

    # ── CLOB live fill streaming ─────────────────────────────────────────────

    async def stream_clob_fills(
        self,
        market_id: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """
        Fetch recent fills from the CLOB /fills endpoint and filter for whales (>$100).

        NOTE: This is a DIFFERENT method from get_recent_fills() which hits
        settings.POLYMARKET_API_HOST/trades. This method hits the dedicated
        /fills endpoint on CLOB_HOST and is used exclusively by stream_live_trades().
        """
        client = await self._get_http()
        params: dict = {"limit": limit}
        if market_id:
            params["market"] = market_id

        try:
            resp = await client.get(f"{CLOB_HOST}/fills", params=params)
            resp.raise_for_status()
            fills: list[dict] = list(resp.json())
            # Whale filter: only fills with notional > $100
            return [f for f in fills if float(f.get("size", 0)) * float(f.get("price", 0)) > 100]
        except Exception as exc:
            logger.error("Failed to fetch CLOB fills: %s", exc)
            return []

    async def stream_live_trades(self) -> None:
        """
        Background task: poll CLOB fills every 5s → deduplicate → save to DB
        → broadcast via WebSocket to connected frontend clients.

        Start this in the FastAPI lifespan with asyncio.create_task().
        """
        logger.info("CLOB live trade stream started (5s poll)")
        seen_fill_ids: set[str] = set()

        while True:
            try:
                fills = await self.stream_clob_fills(limit=30)
                if fills:
                    async with async_session_factory() as db:
                        for fill in fills:
                            # BUG-6 fix: deduplicate by fill_id
                            fill_id = str(
                                fill.get("transactionHash")
                                or fill.get("id")
                                or fill.get("fillId")
                                or ""
                            )
                            if not fill_id or fill_id in seen_fill_ids:
                                continue
                            seen_fill_ids.add(fill_id)
                            # Keep seen_fill_ids bounded (last 1000)
                            if len(seen_fill_ids) > 1000:
                                seen_fill_ids.pop()

                            trade = Trade(
                                fill_id=fill_id,
                                market_id=str(fill.get("market", "")),
                                size=float(fill.get("size", 0)),
                                price=float(fill.get("price", 0)),
                                side=str(fill.get("side", "unknown")),
                                maker_fee=float(fill.get("makerFee", fill.get("maker_fee", 0))),
                                taker_fee=float(fill.get("takerFee", fill.get("taker_fee", 0))),
                            )
                            db.add(trade)

                        await db.commit()

                    # Broadcast each new trade to WS clients
                    for fill in fills:
                        fill_id = str(fill.get("transactionHash") or fill.get("id") or "")
                        if fill_id in seen_fill_ids:
                            trade_dict = {
                                "fill_id": fill_id,
                                "market_id": fill.get("market", ""),
                                "size": float(fill.get("size", 0)),
                                "price": float(fill.get("price", 0)),
                                "side": fill.get("side", "unknown"),
                                "value_usd": round(
                                    float(fill.get("size", 0)) * float(fill.get("price", 0)),
                                    2,
                                ),
                            }
                            await _broadcast_whale_trade(trade_dict)

                await asyncio.sleep(5.0)

            except Exception as exc:
                logger.error("Live trade stream error (will retry): %s", exc)
                await asyncio.sleep(10.0)


# Module-level singleton
polymarket_client = PolymarketClient()


async def create_empty_market_data() -> list[dict]:
    """Fallback empty market list for startup failure scenarios."""
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
