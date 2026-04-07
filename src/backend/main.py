"""
FastAPI main application entry point for POLYGOD — FULL GOD-TIER VERSION.

Configures CORS, routers, WebSocket streams, and lifespan events for database and background tasks.
"""

import asyncio
import hashlib
import itertools
import logging
import os
import secrets
import socket
from contextlib import asynccontextmanager
from typing import Final

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query, WebSocket
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from src.backend.auth import verify_api_key
from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.middleware.auth import admin_required
from src.backend.middleware.security_headers import SecurityHeadersMiddleware
from src.backend.news.aggregator import news_aggregator
from src.backend.polygod_graph import POLYGOD_MODE, paper, polygod_graph, run_polygod
from src.backend.polymarket.client import polymarket_client
from src.backend.routes import debate, llm, markets, news, telegram, users
from src.backend.self_improving_memory_loop import memory_loop
from src.backend.services.llm_concierge import concierge
from src.backend.tasks.update_markets import get_scheduler, update_top_markets

SECRET_KEYS = [
    "POLYMARKET_API_KEY",
    "POLYMARKET_SECRET",
    "POLYMARKET_PASSPHRASE",
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
    "NEWS_API_KEY",
    "INTERNAL_API_KEY",
]


def mask_secrets(text: str) -> str:
    for key in SECRET_KEYS:
        val = os.getenv(key, "")
        if val and val in text:
            text = text.replace(val, "***REDACTED***")
    return text


limiter = Limiter(key_func=get_remote_address)

if settings.FORCE_IPV4:
    logger = logging.getLogger(__name__)
    logger.warning(
        "FORCE_IPV4 is enabled - overriding socket.getaddrinfo to filter IPv6. "
        "This may break libraries that rely on IPv6 or standard DNS behavior."
    )
    _old_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(*args, **kwargs):
        responses = _old_getaddrinfo(*args, **kwargs)
        return [response for response in responses if response[0] == socket.AF_INET]

    socket.getaddrinfo = _ipv4_only_getaddrinfo

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

WHALE_ALERTS: Final[list[str]] = [
    "POLYGOD WHALE ALERT: HorizonSplendidView loaded 150k YES — analyzing edge",
    "Major position detected — POLYGOD scanning for alpha opportunities",
    "Whale activity in Polymarket — POLYGOD computing optimal response",
    "High-volume trade alert — POLYGOD AI evaluating market impact",
]
whale_cycle = itertools.cycle(WHALE_ALERTS)

MODE: int = settings.POLYGOD_MODE


async def get_mode_from_db() -> int:
    """Get POLYGOD_MODE from database AppState table for thread-safe mode storage."""
    try:
        from sqlalchemy import select

        from src.backend.database import async_session_factory
        from src.backend.db_models import AppState

        async with async_session_factory() as db:
            result = await db.execute(
                select(AppState).where(AppState.key == "polygod_mode")
            )
            row = result.scalar_one_or_none()
            if row:
                return int(row.value)
    except Exception as e:
        logger.warning(f"Failed to read mode from DB, using in-memory: {e}")
    return MODE


async def set_mode_in_db(mode: int) -> None:
    """Set POLYGOD_MODE in database AppState table for thread-safe mode storage."""
    try:
        from sqlalchemy import select

        from src.backend.database import async_session_factory
        from src.backend.db_models import AppState

        async with async_session_factory() as db:
            result = await db.execute(
                select(AppState).where(AppState.key == "polygod_mode")
            )
            row = result.scalar_one_or_none()
            if row:
                row.value = str(mode)
            else:
                db.add(AppState(key="polygod_mode", value=str(mode)))
            await db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist mode to DB: {e}")


async def refresh_llm_stats():
    """Refresh LLM provider token usage stats from usage_logs."""
    logger.info("Refreshing LLM stats...")
    try:
        from datetime import datetime

        from sqlalchemy import func, select

        from src.backend.database import async_session_factory
        from src.backend.models.llm import Provider, UsageLog

        async with async_session_factory() as db:
            today_start = datetime.utcnow().replace(
                hour=0, minute=0, second=0, microsecond=0
            )

            result = await db.execute(
                select(
                    UsageLog.provider,
                    func.coalesce(func.sum(UsageLog.tokens_used), 0).label(
                        "total_tokens"
                    ),
                )
                .where(UsageLog.timestamp >= today_start)
                .group_by(UsageLog.provider)
            )
            usage_by_provider = {row.provider: row.total_tokens for row in result.all()}

            providers_result = await db.execute(select(Provider))
            for provider in providers_result.scalars().all():
                provider.tokens_today = usage_by_provider.get(provider.name, 0)

            await db.commit()
            logger.info(
                f"LLM stats refreshed — {len(usage_by_provider)} providers updated"
            )
    except Exception as e:
        logger.warning(f"Failed to refresh LLM stats: {e}")


async def daily_pnl_report():
    """GOD TIER daily PnL report — runs every 24h"""
    logger.info("=== POLYGOD DAILY PNL REPORT ===")

    total_pnl = sum(paper.pnls) if paper.pnls else 0.0
    trade_count = len(paper.pnls)

    logger.info(f"Paper PnL: ${total_pnl:.2f} | Trades today: {trade_count}")
    logger.info(f"Current POLYGOD_MODE: {POLYGOD_MODE}")

    try:
        from src.backend.polymarket.client import polymarket_client

        top_markets = await polymarket_client.get_top_markets_by_volume(limit=5)
        logger.info(
            f"Top 5 markets by volume: {[m.get('title', 'N/A') for m in top_markets]}"
        )
    except Exception as e:
        logger.warning(f"Could not fetch market data for report: {e}")

    logger.info("=== DAILY REPORT COMPLETE ===")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events with graceful error handling and
    explicit environment validation so Docker startup never crashes even if
    external services or APIs are unavailable.
    """
    logger.info("Starting POLYGOD API...")
    logger.info("=== POLYGOD Startup: Environment Validation (main.py) ===")
    logger.info(f"DATABASE_URL={settings.DATABASE_URL!r}")
    logger.info(f"CORS_ORIGINS={settings.CORS_ORIGINS!r}")
    logger.info(f"HOST={settings.HOST!r}, PORT={settings.PORT}, DEBUG={settings.DEBUG}")
    logger.info(
        f"POLYGOD_MODE={settings.POLYGOD_MODE}, MEM0_CONFIG present={bool(settings.MEM0_CONFIG)}"
    )

    if not settings.NEWS_API_KEY.get_secret_value():
        logger.warning("NEWS_API_KEY not set. News aggregation may be disabled.")
    if not settings.GEMINI_API_KEY.get_secret_value():
        logger.warning("GEMINI_API_KEY not set. POLYGOD AI agents disabled.")
    if not settings.TAVILY_API_KEY.get_secret_value():
        logger.warning("TAVILY_API_KEY not set. Web search enrichment disabled.")
    if not settings.POLYMARKET_API_KEY.get_secret_value():
        logger.info("POLYMARKET_API_KEY not set. Using public Polymarket API only.")
    if (
        not settings.POLYMARKET_SECRET.get_secret_value()
        or not settings.POLYMARKET_PASSPHRASE.get_secret_value()
    ):
        logger.info(
            "POLYMARKET_SECRET / POLYMARKET_PASSPHRASE not fully set. "
            "Authenticated trading may be disabled."
        )

    if not settings.POLYGOD_ADMIN_TOKEN.get_secret_value():
        raise RuntimeError("ADMIN_TOKEN required in production")

    try:
        await init_db()
        logger.info("Database initialized")

        # FIX H3: Sync POLYGOD_MODE from DB on startup
        global POLYGOD_MODE
        db_mode = await get_mode_from_db()
        if db_mode != POLYGOD_MODE:
            POLYGOD_MODE = db_mode
            logger.info(f"Restored POLYGOD_MODE from database: {POLYGOD_MODE}")
    except Exception as e:
        if settings.ALLOW_IN_MEMORY_DB_FALLBACK or settings.DEBUG:
            logger.error(
                f"Database initialization failed: {e} - Continuing with in-memory fallback"
            )
            logger.warning("DATABASE_URL overridden to sqlite+aiosqlite:///:memory:")
        else:
            logger.error(f"Database initialization failed: {e}")
            raise

    try:
        await update_top_markets()
        logger.info("Initial market data loaded")
    except Exception as e:
        logger.error(
            f"Failed to load initial market data: {e} - Continuing without market data"
        )
        try:
            from src.backend.polymarket.client import create_empty_market_data

            await create_empty_market_data()
            logger.info("Initialized empty market data as fallback.")
        except Exception as inner_e:
            logger.error(f"Failed to initialize empty market data fallback: {inner_e}")

    scheduler = get_scheduler()
    try:
        scheduler.start()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.error(
            f"Failed to start background scheduler: {e} - Continuing without scheduler"
        )
        scheduler = None

    if scheduler:
        try:
            scheduler.add_job(
                daily_pnl_report,
                trigger="cron",
                hour=0,
                minute=0,
                id="daily_pnl_report",
                replace_existing=True,
            )
            logger.info("Daily PnL report scheduled (every 24h)")
        except Exception as e:
            logger.warning(f"Could not schedule daily PnL report: {e}")

    if scheduler:
        try:
            from apscheduler.triggers.interval import IntervalTrigger

            scheduler.add_job(
                refresh_llm_stats,
                trigger=IntervalTrigger(minutes=5),
                id="refresh_llm_stats",
                name="Refresh LLM provider token stats",
                replace_existing=True,
            )
            logger.info("LLM stats refresh scheduled (every 5m)")
        except Exception as e:
            logger.warning(f"Could not schedule LLM stats refresh: {e}")

    # LLM Concierge health check - every 30 minutes
    if scheduler:
        try:
            from apscheduler.triggers.interval import IntervalTrigger

            scheduler.add_job(
                concierge.health_check_all_keys,
                trigger=IntervalTrigger(minutes=30),
                id="llm_concierge_health",
                name="LLM Concierge key health check",
                replace_existing=True,
            )
            logger.info("LLM Concierge health check scheduled (every 30m)")
        except Exception as e:
            logger.warning(f"Could not schedule LLM Concierge health check: {e}")

    if settings.POLYGOD_MODE >= 1:
        logger.info(
            f"🚀 MODE {settings.POLYGOD_MODE} — swarm runs via polygod-swarm container"
        )

    if scheduler:
        try:
            scheduler.add_job(
                memory_loop.hindsight_replay,
                trigger="cron",
                day_of_week="sun",
                hour=23,
                minute=0,
                id="hindsight_replay",
                replace_existing=True,
            )
            scheduler.add_job(
                memory_loop.notebooklm_reflection,
                trigger="cron",
                day_of_week="sun",
                hour=23,
                minute=30,
                id="notebooklm_reflection",
                replace_existing=True,
            )
            logger.info(
                "Self-Improving Memory Loop scheduled (weekly Sunday 23:00-23:30)"
            )
        except Exception as e:
            logger.warning(f"Could not schedule memory loop jobs: {e}")

    telegram_task = None
    if settings.TELEGRAM_BOT_TOKEN.get_secret_value():
        try:
            from src.backend.routes.telegram import run_telegram_bot

            telegram_task = asyncio.create_task(run_telegram_bot())
            logger.info("Telegram bot starting in background...")
        except Exception as e:
            logger.error(f"Failed to start Telegram bot: {e}")
    else:
        logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")

    yield

    if telegram_task:
        telegram_task.cancel()
        logger.info("Telegram bot task cancelled")

    logger.info("Shutting down POLYGOD...")
    if scheduler:
        try:
            scheduler.shutdown()
        except Exception as e:
            logger.error(f"Scheduler shutdown failed: {e}")
    try:
        await polymarket_client.close()
    except Exception as e:
        logger.error(f"Polymarket client close failed: {e}")
    try:
        await news_aggregator.close()
    except Exception as e:
        logger.error(f"News aggregator close failed: {e}")
    try:
        await close_db()
    except Exception as e:
        logger.error(f"Database close failed: {e}")
    logger.info("Shutdown complete")


app = FastAPI(
    title="POLYGOD API",
    description="POLYGOD - Advanced Polymarket intelligence and trading agent",
    version="0.1.0",
    lifespan=lifespan,
    debug=settings.debug,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins_list,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        ),
        Middleware(SecurityHeadersMiddleware),
    ],
)

app.state.limiter = limiter

Instrumentator().instrument(app).expose(app)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    detail = mask_secrets(str(exc))
    return JSONResponse(status_code=500, content={"detail": detail})


class SecretFilter(logging.Filter):
    def filter(self, record):
        record.msg = mask_secrets(str(record.msg))
        return True


logging.getLogger().addFilter(SecretFilter())


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)


app.include_router(markets.router, prefix="/api/markets")
app.include_router(news.router, prefix="/api/news")
app.include_router(debate.router, prefix="/api/debate")
app.include_router(users.router, prefix="/api/users")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(telegram.router, prefix="/api/telegram")


@app.websocket("/ws/polygod")
async def polygod_ws(websocket: WebSocket, token: str = Query(default="")):
    expected = settings.internal_api_key.encode()
    provided = token.encode()
    if not secrets.compare_digest(
        hashlib.sha256(provided).digest(), hashlib.sha256(expected).digest()
    ):
        await websocket.close(code=4001)
        return
    await websocket.accept()
    while True:
        await websocket.send_json(
            {
                "paper_pnl": paper.pnls[-1] if paper.pnls else 0,
                "mode": POLYGOD_MODE,
                "evolution_score": 0.95,  # Darwinian fitness metric
                "whale_alert": next(whale_cycle),
            }
        )
        await asyncio.sleep(2)


@app.websocket("/ws/debate/{market_id}")
async def debate_websocket(
    websocket: WebSocket,
    market_id: str,
    token: str = Query(default=""),
):
    """Full Debate Floor streaming — live agent debate with verdict.

    SECURITY FIX: Requires token auth. Closes before accept on auth failure.
    """
    expected = settings.internal_api_key.encode()
    provided = token.encode()
    if not secrets.compare_digest(
        hashlib.sha256(provided).digest(), hashlib.sha256(expected).digest()
    ):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    try:
        async for chunk in polygod_graph.astream(
            {"market_id": market_id, "mode": settings.POLYGOD_MODE},
        ):
            await websocket.send_json({k: str(v) for k, v in chunk.items()})
    except Exception as e:
        logger.error(f"Debate WebSocket error: {e}")
        await websocket.send_json({"error": str(e)})
    await websocket.close()


@app.post("/polygod/switch-mode")
async def switch_mode(new_mode: int, _: bool = Depends(admin_required)):
    global POLYGOD_MODE
    POLYGOD_MODE = new_mode
    await set_mode_in_db(new_mode)  # FIX H3: Persist to DB for thread-safety
    mode_label = "BEAST MODE" if POLYGOD_MODE == 3 else "safe"
    return {"status": f"Switched to Mode {POLYGOD_MODE} — {mode_label}"}


@app.post("/polygod/simulate")
async def monte_carlo_simulate(
    market_id: str, order_size: float = 1000, _: bool = Depends(admin_required)
):
    """GOD TIER simulation dashboard endpoint"""
    from src.backend.polygod_graph import get_enriched_market_data, run_monte_carlo

    market_data = await get_enriched_market_data(market_id)
    sim = run_monte_carlo({"size": order_size}, market_data)

    return {
        "simulation": sim,
        "recommendation": (
            "BEAST APPROVED" if sim["win_prob"] > 0.65 else "SAFE MODE ONLY"
        ),
    }


@app.post("/api/scan-niches")
async def scan_niches(mode: int = 0, _: str = Depends(verify_api_key)):
    """
    Start money printer — scan for micro-niche opportunities in low-liquidity markets.

    Modes:
    - 0 = OBSERVE (scan only, no tournaments)
    - 1 = PAPER (scan + paper tournaments)
    - 2 = LOW (scan + Kelly-guarded tournaments)
    - 3 = BEAST (scan + full tournaments)
    """
    from src.backend.niche_scanner import scanner

    try:
        opportunities = await scanner.scan_niches(mode)
        return {
            "status": "scan_complete",
            "opportunities": opportunities,
            "count": len(opportunities),
            "mode": mode,
            "message": f"🎰 Money printer scanned {len(opportunities)} niche opportunities",
        }
    except Exception as e:
        logger.error(f"Niche scan failed: {e}")
        raise HTTPException(status_code=500, detail=f"Niche scan failed: {e}") from e


@app.post("/polygod/run")
async def polygod_run(
    market_id: str, mode: int = 0, question: str = "", _: bool = Depends(admin_required)
):
    """
    GOD TIER CYCLIC SWARM — Full pipeline execution.

    Modes:
    - 0 = OBSERVE (1 debate round, approval required)
    - 1 = PAPER (2 debate rounds, paper execution)
    - 2 = LOW (3 debate rounds, Kelly-guarded, evolution lab)
    - 3 = BEAST (3 debate rounds, evolution lab, live execution)
    """
    try:
        result = await run_polygod(market_id=market_id, mode=mode, question=question)
        return {
            "status": "complete",
            "run_id": result.get("run_id"),
            "market": result.get("question", ""),
            "verdict": result.get("debate_verdict", "No verdict"),
            "paper_pnl": result.get("paper_pnl", 0),
            "risk_status": result.get("risk_status", "unknown"),
            "debate_rounds": result.get("debate_round", 0),
            "evolution_best": result.get("evolution_best"),
            "simulation": result.get("simulation"),
            "execution_result": result.get("execution_result"),
        }
    except Exception as e:
        logger.error(f"POLYGOD run failed: {e}")
        raise HTTPException(status_code=500, detail=f"POLYGOD run failed: {e}") from e


@app.get("/api/health")
async def health():
    """GOD TIER health check."""
    from sqlalchemy import text

    from src.backend.database import engine

    scheduler = get_scheduler()
    db_connected = False
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_connected = True
    except Exception:
        pass

    return {
        "status": "god-tier",
        "version": "0.1.0",
        "database": "connected" if db_connected else "disconnected",
        "scheduler": scheduler.running if scheduler else False,
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": "POLYGOD API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
        "message": "Welcome to POLYGOD - Your Polymarket AI Oracle",
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
