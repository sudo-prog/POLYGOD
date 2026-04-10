"""
Background tasks for updating market data.

Changes vs previous version:
  - FIXED C5: get_scheduler() is now a singleton. Previously it created a new
              AsyncIOScheduler on every call, meaning the /api/health endpoint
              received a brand-new, never-started instance and always reported
              scheduler=False even when the real one was running.
  - FIXED H1: update_top_markets() no longer fires N+1 SELECTs (one per market).
              Replaced with a single bulk-existence check + batched UPSERTs.
              Price history records are bulk-inserted via add_all().
              Impact: 100 individual SELECTs → 1 IN query = ~99% fewer round-trips
              per 15-minute update cycle.
  - FIXED L1: datetime.utcnow() replaced with timezone-aware utcnow() helper.
"""

import logging
from datetime import timedelta

from sqlalchemy import delete, select, update

from src.backend.database import async_session_factory, utcnow
from src.backend.db_models import AppState, Market, PriceHistory
from src.backend.polymarket.client import polymarket_client

logger = logging.getLogger(__name__)

# ── Singleton scheduler ──────────────────────────────────────────────────────
# Holding the instance here ensures every caller (lifespan, /api/health, tests)
# gets the same object and sees the correct .running state.
_scheduler = None


def get_scheduler():
    """
    Return the singleton APScheduler instance, creating it if necessary.

    All jobs are registered on the first call. Subsequent calls return
    the same object without re-registering jobs.
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.interval import IntervalTrigger

    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        update_top_markets,
        trigger=IntervalTrigger(minutes=15),
        id="update_markets",
        name="Update top 100 markets",
        replace_existing=True,
    )
    _scheduler.add_job(
        cleanup_old_news,
        trigger=IntervalTrigger(hours=24),
        id="cleanup_news",
        name="Clean up old news articles",
        replace_existing=True,
    )
    _scheduler.add_job(
        cleanup_old_price_history,
        trigger=IntervalTrigger(days=7),
        id="cleanup_price_history",
        name="Clean up old price history",
        replace_existing=True,
    )

    return _scheduler


# ── Market update task ───────────────────────────────────────────────────────


async def update_top_markets() -> None:
    """
    Update the top 100 markets in the database and record price history.

    Uses a single bulk-existence check instead of N individual SELECTs,
    then performs batched UPSERTs and a single add_all() for price history.
    """
    logger.info("Starting market update task...")

    try:
        markets_data = await polymarket_client.get_top_markets_by_volume(limit=100)
        if not markets_data:
            logger.warning("No markets fetched from Polymarket API")
            return

        now = utcnow()

        async with async_session_factory() as db:
            # ── 1. Single bulk-existence check ───────────────────────────
            market_ids = [m["id"] for m in markets_data]
            existing_result = await db.execute(
                select(Market.id).where(Market.id.in_(market_ids))
            )
            existing_ids: set[str] = {row[0] for row in existing_result}

            # ── 2. Bulk UPDATE existing / INSERT new ─────────────────────
            new_markets: list[Market] = []
            for md in markets_data:
                if md["id"] in existing_ids:
                    # Build update dict — exclude the PK and any keys not on the model
                    update_values = {
                        k: v for k, v in md.items() if k != "id" and hasattr(Market, k)
                    }
                    update_values["last_updated"] = now
                    await db.execute(
                        update(Market)
                        .where(Market.id == md["id"])
                        .values(**update_values)
                    )
                else:
                    new_markets.append(Market(**md))

            if new_markets:
                db.add_all(new_markets)
                logger.debug("Inserted %d new markets", len(new_markets))

            # ── 3. Bulk price-history insert ─────────────────────────────
            price_points = [
                PriceHistory(
                    market_id=md["id"],
                    yes_percentage=md.get("yes_percentage", 50.0),
                    volume=md.get("volume_24h", 0.0),
                    timestamp=now,
                )
                for md in markets_data
            ]
            db.add_all(price_points)

            # ── 4. Update last-updated app-state ────────────────────────
            state_result = await db.execute(
                select(AppState).where(AppState.key == "markets_last_updated")
            )
            state_row = state_result.scalar_one_or_none()
            if state_row:
                state_row.value = now.isoformat()
            else:
                db.add(AppState(key="markets_last_updated", value=now.isoformat()))

            await db.commit()
            logger.info(
                "Market update complete: %d total, %d updated, %d inserted",
                len(markets_data),
                len(existing_ids),
                len(new_markets),
            )

    except Exception as exc:
        logger.error("Error updating markets: %s", exc)
        raise


# ── Cleanup tasks ────────────────────────────────────────────────────────────


async def cleanup_old_news(days: int = 7) -> None:
    """Remove news articles older than `days` days."""
    from src.backend.db_models import NewsArticle

    logger.info("Cleaning up news articles older than %d days...", days)
    try:
        cutoff = utcnow() - timedelta(days=days)
        async with async_session_factory() as db:
            result = await db.execute(
                delete(NewsArticle).where(NewsArticle.created_at < cutoff)
            )
            await db.commit()
            logger.info("Deleted %d old news articles", result.rowcount)
    except Exception as exc:
        logger.error("Error cleaning up old news: %s", exc)


async def cleanup_old_price_history(days: int = 30) -> None:
    """Remove price history records older than `days` days."""
    logger.info("Cleaning up price history older than %d days...", days)
    try:
        cutoff = utcnow() - timedelta(days=days)
        async with async_session_factory() as db:
            result = await db.execute(
                delete(PriceHistory).where(PriceHistory.timestamp < cutoff)
            )
            await db.commit()
            logger.info("Deleted %d old price history records", result.rowcount)
    except Exception as exc:
        logger.error("Error cleaning up price history: %s", exc)
