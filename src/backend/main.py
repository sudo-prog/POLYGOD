"""
FastAPI main application entry point for POLYGOD.

Changes vs previous version:
  - FIXED C5: /api/health now uses the singleton get_scheduler() so it reports
              the actual running scheduler, not a new dead instance.
  - FIXED H2: Both WebSocket handlers now catch WebSocketDisconnect and RuntimeError
              so client disconnects are handled gracefully without leaking coroutines.
  - FIXED H4: Debate WebSocket no longer sends raw exception messages to the client
              (which could leak internal details). Logs the full error; sends a
              generic message to the client.
  - FIXED M1: mask_secrets() pre-computes the set of secret values at startup
              instead of re-reading os.getenv on every call.
  - FIXED C4: POLYGOD_ADMIN_TOKEN check moved to lifespan only (not at validator
              level) so dev startup isn't blocked.
  - FIXED L1: datetime.utcnow() → utcnow() helper from database module.
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
from fastapi import Depends, FastAPI, HTTPException, WebSocket
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.websockets import WebSocketDisconnect

from src.backend.auth import verify_api_key
from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.middleware.auth import admin_required
from src.backend.middleware.security_headers import SecurityHeadersMiddleware
from src.backend.news.aggregator import news_aggregator
from src.backend.polygod_graph import POLYGOD_MODE, paper, polygod_graph, run_polygod
from src.backend.polymarket.client import polymarket_client
from src.backend.routes import debate, llm, markets, news, telegram, users
from src.backend.self_improving_memory_loop import forgetting_engine, memory_loop
from src.backend.services.llm_concierge import concierge
from src.backend.tasks.update_markets import get_scheduler, update_top_markets

# ── Secret masking — pre-computed at module load time ────────────────────────
# FIXED M1: Reading os.getenv on every log statement was O(n) env lookups per
# exception. Build the set once; replace values in O(k) string scans where k
# is the number of secrets actually set.

_SECRET_KEYS: Final[tuple[str, ...]] = (
    "POLYMARKET_API_KEY",
    "POLYMARKET_SECRET",
    "POLYMARKET_PASSPHRASE",
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
    "NEWS_API_KEY",
    "INTERNAL_API_KEY",
    "POLYGOD_ADMIN_TOKEN",
    "ENCRYPTION_KEY",
    "TELEGRAM_BOT_TOKEN",
    "X_BEARER_TOKEN",
)

# Frozenset of non-empty secret values known at startup.
_SECRET_VALUES: frozenset[str] = frozenset(
    v for k in _SECRET_KEYS if (v := os.getenv(k, "")) and len(v) > 4
)


def mask_secrets(text: str) -> str:
    """Replace any known secret values in `text` with '***REDACTED***'."""
    for val in _SECRET_VALUES:
        if val in text:
            text = text.replace(val, "***REDACTED***")
    return text


# ── Rate limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── Optional IPv4 override ───────────────────────────────────────────────────
if settings.FORCE_IPV4:
    _old_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(*args, **kwargs):
        return [r for r in _old_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]

    socket.getaddrinfo = _ipv4_only_getaddrinfo

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class _SecretFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = mask_secrets(str(record.msg))
        if record.args:
            record.args = tuple(mask_secrets(str(a)) for a in record.args)
        return True


logging.getLogger().addFilter(_SecretFilter())

# ── Whale-alert cycle (static demo data) ─────────────────────────────────────
_WHALE_ALERTS: Final[list[str]] = [
    "POLYGOD WHALE ALERT: HorizonSplendidView loaded 150k YES — analysing edge",
    "Major position detected — POLYGOD scanning for alpha opportunities",
    "Whale activity in Polymarket — POLYGOD computing optimal response",
    "High-volume trade alert — POLYGOD AI evaluating market impact",
]
_whale_cycle = itertools.cycle(_WHALE_ALERTS)

MODE: int = settings.POLYGOD_MODE


# ── DB-backed mode helpers ────────────────────────────────────────────────────


async def get_mode_from_db() -> int:
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
    except Exception as exc:
        logger.warning("Failed to read mode from DB, using in-memory: %s", exc)
    return MODE


async def set_mode_in_db(mode: int) -> None:
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
    except Exception as exc:
        logger.warning("Failed to persist mode to DB: %s", exc)


# ── Scheduled helpers ─────────────────────────────────────────────────────────


async def refresh_llm_stats() -> None:
    """Refresh LLM provider token-usage stats from usage_logs."""
    logger.info("Refreshing LLM stats...")
    try:
        from datetime import datetime, timezone

        from sqlalchemy import func, select

        from src.backend.database import async_session_factory
        from src.backend.models.llm import Provider, UsageLog

        async with async_session_factory() as db:
            today_start = datetime.now(timezone.utc).replace(
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
                "LLM stats refreshed — %d providers updated", len(usage_by_provider)
            )
    except Exception as exc:
        logger.warning("Failed to refresh LLM stats: %s", exc)


async def daily_pnl_report() -> None:
    """Daily PnL summary — runs every 24h via APScheduler."""
    total_pnl = sum(paper.pnls) if paper.pnls else 0.0
    trade_count = len(paper.pnls)
    logger.info(
        "=== POLYGOD DAILY PNL REPORT: $%.2f | Trades: %d | Mode: %d ===",
        total_pnl,
        trade_count,
        POLYGOD_MODE,
    )
    try:
        top_markets = await polymarket_client.get_top_markets_by_volume(limit=5)
        logger.info(
            "Top 5 markets by volume: %s",
            [m.get("title", "N/A") for m in top_markets],
        )
    except Exception as exc:
        logger.warning("Could not fetch market data for daily report: %s", exc)


# ── Application lifespan ──────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup + shutdown lifecycle with graceful error handling."""
    logger.info("Starting POLYGOD API...")
    logger.info(
        "DATABASE_URL=%r | CORS=%r | HOST=%r:%d | DEBUG=%s | MODE=%d",
        settings.DATABASE_URL,
        settings.CORS_ORIGINS,
        settings.HOST,
        settings.PORT,
        settings.DEBUG,
        settings.POLYGOD_MODE,
    )

    # ── Hard production guard ───────────────────────────────────────────────
    # Validation in config.py warns in DEBUG mode; here we hard-fail for prod.
    if not settings.DEBUG:
        admin_token = settings.POLYGOD_ADMIN_TOKEN.get_secret_value()
        if not admin_token or admin_token == "change-this-before-use":
            raise RuntimeError(
                "POLYGOD_ADMIN_TOKEN must be set to a strong value before starting "
                "in production. Set DEBUG=true in .env to bypass this check in development."
            )

    # ── Database ─────────────────────────────────────────────────────────────
    try:
        await init_db()
        logger.info("Database initialised")
        global POLYGOD_MODE
        db_mode = await get_mode_from_db()
        if db_mode != POLYGOD_MODE:
            POLYGOD_MODE = db_mode
            logger.info("Restored POLYGOD_MODE from database: %d", POLYGOD_MODE)
    except Exception as exc:
        if settings.ALLOW_IN_MEMORY_DB_FALLBACK or settings.DEBUG:
            logger.error("Database init failed: %s — continuing with fallback", exc)
        else:
            logger.error("Database init failed: %s", exc)
            raise

    # ── Initial market data ───────────────────────────────────────────────────
    try:
        await update_top_markets()
        logger.info("Initial market data loaded")
    except Exception as exc:
        logger.error("Failed to load initial market data: %s — continuing", exc)

    # ── Scheduler ───────────────────────────────────────────────────────────
    # FIXED C5: get_scheduler() is a singleton — this is the same instance
    # that /api/health will later inspect.
    scheduler = get_scheduler()
    try:
        scheduler.start()
        logger.info("Background scheduler started")
    except Exception as exc:
        logger.error("Failed to start background scheduler: %s", exc)

    def _add_job(func, **kwargs):
        """Helper to add a scheduler job with consistent error logging."""
        try:
            scheduler.add_job(func, replace_existing=True, **kwargs)
        except Exception as exc:
            logger.warning("Could not schedule %s: %s", func.__name__, exc)

    from apscheduler.triggers.interval import IntervalTrigger

    _add_job(daily_pnl_report, trigger="cron", hour=0, minute=0, id="daily_pnl_report")
    _add_job(
        refresh_llm_stats,
        trigger=IntervalTrigger(minutes=5),
        id="refresh_llm_stats",
        name="Refresh LLM provider token stats",
    )
    _add_job(
        concierge.health_check_all_keys,
        trigger=IntervalTrigger(minutes=30),
        id="llm_concierge_health",
        name="LLM Concierge key health check",
    )
    _add_job(
        memory_loop.hindsight_replay,
        trigger="cron",
        day_of_week="sun",
        hour=23,
        minute=0,
        id="hindsight_replay",
    )
    _add_job(
        memory_loop.notebooklm_reflection,
        trigger="cron",
        day_of_week="sun",
        hour=23,
        minute=30,
        id="notebooklm_reflection",
    )
    _add_job(
        forgetting_engine.prune,
        trigger=IntervalTrigger(hours=6),
        id="forgetting_engine_prune",
        name="Prune low-signal memories",
    )

    if settings.POLYGOD_MODE >= 1:
        logger.info(
            "🚀 MODE %d — swarm runs via polygod-swarm container", settings.POLYGOD_MODE
        )

    # ── Telegram bot ─────────────────────────────────────────────────────────
    telegram_task = None
    if settings.TELEGRAM_BOT_TOKEN.get_secret_value():
        try:
            from src.backend.routes.telegram import run_telegram_bot

            telegram_task = asyncio.create_task(run_telegram_bot())
            logger.info("Telegram bot starting in background...")
        except Exception as exc:
            logger.error("Failed to start Telegram bot: %s", exc)
    else:
        logger.info("TELEGRAM_BOT_TOKEN not set — Telegram bot disabled")

    yield  # ── Application running ───────────────────────────────────────────

    # ── Shutdown ────────────────────────────────────────────────────────────
    if telegram_task:
        telegram_task.cancel()
        logger.info("Telegram bot task cancelled")

    logger.info("Shutting down POLYGOD...")
    try:
        scheduler.shutdown()
    except Exception as exc:
        logger.error("Scheduler shutdown failed: %s", exc)
    try:
        await polymarket_client.close()
    except Exception as exc:
        logger.error("Polymarket client close failed: %s", exc)
    try:
        await news_aggregator.close()
    except Exception as exc:
        logger.error("News aggregator close failed: %s", exc)
    try:
        await close_db()
    except Exception as exc:
        logger.error("Database close failed: %s", exc)
    logger.info("Shutdown complete")


# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="POLYGOD API",
    description="POLYGOD — Advanced Polymarket intelligence and trading agent",
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
    logger.error("Unhandled exception: %s", detail)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(markets.router, prefix="/api/markets")
app.include_router(news.router, prefix="/api/news")
# FIXED H5: debate router has its own prefix="/api/debate" set on the APIRouter
# object inside routes_debate.py → remove it there; prefix is set here only.
app.include_router(debate.router, prefix="/api/debate")
# FIXED H6: same issue with users router
app.include_router(users.router, prefix="/api/users")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(telegram.router, prefix="/api/telegram")


# ── WebSocket helpers ──────────────────────────────────────────────────────────


def _authenticate_ws_token(token: str) -> bool:
    """Constant-time comparison of the provided WS token against the configured key."""
    expected = settings.internal_api_key.encode()
    provided = token.encode()
    return secrets.compare_digest(
        hashlib.sha256(provided).digest(),
        hashlib.sha256(expected).digest(),
    )


# ── WebSocket: POLYGOD live state stream ──────────────────────────────────────


# First-message authentication helper
async def _ws_authenticate(websocket: WebSocket) -> bool:
    """
    Wait for a {"type": "auth", "token": "..."} frame on an already-accepted
    WebSocket connection.

    Returns True if authenticated, False (and closes the socket) otherwise.
    """
    try:
        import json as _json

        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        frame = _json.loads(raw)
        if frame.get("type") != "auth":
            await websocket.close(code=4001)
            return False
        token = str(frame.get("token", ""))
        if not _authenticate_ws_token(token):
            await websocket.close(code=4001)
            return False
        return True
    except asyncio.TimeoutError:
        logger.warning("WS auth timed out after 10.0s")
        await websocket.close(code=4008)
        return False
    except Exception as exc:
        logger.warning("WS auth frame parse error: %s", exc)
        await websocket.close(code=4001)
        return False


@app.websocket("/ws/polygod")
async def polygod_ws(websocket: WebSocket):
    """
    Live POLYGOD state stream — first-message auth, then 2s push loop.

    Auth protocol:
      1. Server accepts the upgrade (no token in URL)
      2. Client sends: {"type": "auth", "token": "<INTERNAL_API_KEY>"}
      3. Server confirms: {"type": "auth_ok"}
      4. Server pushes state frames every 2s
    """
    await websocket.accept()
    if not await _ws_authenticate(websocket):
        return

    await websocket.send_json({"type": "auth_ok"})

    try:
        while True:
            await websocket.send_json(
                {
                    "type": "state",
                    "paper_pnl": paper.pnls[-1] if paper.pnls else 0,
                    "mode": POLYGOD_MODE,
                    "evolution_score": 0.95,
                    "whale_alert": next(_whale_cycle),
                }
            )
            await asyncio.sleep(2)
    except (WebSocketDisconnect, RuntimeError):
        logger.info("PolyGod WS client disconnected")
    except Exception as exc:
        logger.error("PolyGod WS unexpected error: %s", exc)
    finally:
        logger.debug("PolyGod WS connection closed")


# ── WebSocket: Debate floor stream ────────────────────────────────────────────


@app.websocket("/ws/debate/{market_id}")
async def debate_websocket(websocket: WebSocket, market_id: str):
    """
    Debate Floor streaming WebSocket — first-message auth.

    Auth protocol: same as /ws/polygod above.
    """
    await websocket.accept()
    if not await _ws_authenticate(websocket):
        return

    await websocket.send_json({"type": "auth_ok"})

    try:
        async for chunk in polygod_graph.astream(
            {"market_id": market_id, "mode": settings.POLYGOD_MODE},
        ):
            await websocket.send_json({k: str(v) for k, v in chunk.items()})
    except (WebSocketDisconnect, RuntimeError):
        logger.info("Debate WS client disconnected for market %s", market_id)
    except Exception as exc:
        logger.error("Debate WebSocket error for market %s: %s", market_id, exc)
        try:
            await websocket.send_json(
                {"type": "error", "content": "Debate terminated unexpectedly"}
            )
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ── REST endpoints ────────────────────────────────────────────────────────────


@app.post("/polygod/switch-mode")
async def switch_mode(new_mode: int, _: bool = Depends(admin_required)):
    global POLYGOD_MODE
    POLYGOD_MODE = new_mode
    await set_mode_in_db(new_mode)
    mode_label = {0: "OBSERVE", 1: "PAPER", 2: "LOW", 3: "BEAST"}.get(
        new_mode, "UNKNOWN"
    )
    return {"status": f"Switched to Mode {POLYGOD_MODE} — {mode_label}"}


@app.post("/polygod/simulate")
async def monte_carlo_simulate(
    market_id: str, order_size: float = 1000, _: bool = Depends(admin_required)
):
    """Monte Carlo simulation endpoint."""
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
    """Scan for micro-niche opportunities in low-liquidity markets."""
    from src.backend.niche_scanner import scanner

    try:
        opportunities = await scanner.scan_niches(mode)
        return {
            "status": "scan_complete",
            "opportunities": opportunities,
            "count": len(opportunities),
            "mode": mode,
        }
    except Exception as exc:
        logger.error("Niche scan failed: %s", exc)
        raise HTTPException(status_code=500, detail="Niche scan failed") from exc


@app.post("/polygod/run")
async def polygod_run(
    market_id: str,
    mode: int = 0,
    question: str = "",
    _: bool = Depends(admin_required),
):
    """Full POLYGOD cyclic swarm pipeline."""
    try:
        result = await run_polygod(market_id=market_id, mode=mode, question=question)
        return {
            "status": "complete",
            "run_id": result.get("run_id"),
            "market": result.get("question", ""),
            "verdict": result.get("verdict", "No verdict"),
            "paper_pnl": result.get("paper_pnl", 0),
            "risk_status": result.get("risk_status", "unknown"),
            "debate_rounds": result.get("debate_round", 0),
            "evolution_best": result.get("evolution_best"),
            "simulation": result.get("simulation"),
            "execution_result": result.get("execution_result"),
        }
    except Exception as exc:
        logger.error("POLYGOD run failed: %s", exc)
        raise HTTPException(status_code=500, detail="POLYGOD run failed") from exc


@app.get("/api/health")
async def health():
    """
    Health check endpoint.

    FIXED C5: Uses the singleton get_scheduler() so .running reflects the
    actual scheduler started during lifespan, not a new dead instance.
    """
    from sqlalchemy import text

    from src.backend.database import engine

    # FIXED C5: singleton — same object started during lifespan
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
        "polygod_mode": POLYGOD_MODE,
    }


@app.get("/")
async def root() -> dict:
    return {
        "name": "POLYGOD API",
        "version": "0.1.0",
        "docs": "/docs" if settings.DEBUG else "disabled in production",
        "health": "/api/health",
    }


if __name__ == "__main__":
    uvicorn.run(
        "src.backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
