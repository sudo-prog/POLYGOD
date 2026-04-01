"""
FastAPI main application entry point for POLYGOD.

Configures CORS, routers, and lifespan events for database and background tasks.
"""

import asyncio
import logging
import socket
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Final
import itertools

import uvicorn
from fastapi import FastAPI, WebSocket, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.news.aggregator import news_aggregator
from src.backend.polygod_graph import polygod_graph, paper, POLYGOD_MODE, run_polygod
from src.backend.polymarket.client import polymarket_client
from src.backend.routes import debate, markets, news, users
from src.backend.tasks.update_markets import get_scheduler, update_top_markets
from prometheus_fastapi_instrumentator import Instrumentator

# Force IPv4 to avoid IPv6 timeouts (helps in some Docker/network setups)
# Only apply if FORCE_IPV4 is explicitly enabled to avoid unintended side effects
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

# Configure logging (basic config; can be overridden if app embeds this)
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Whale alert messages
WHALE_ALERTS: Final[list[str]] = [
    "POLYGOD WHALE ALERT: HorizonSplendidView loaded 150k YES — analyzing edge",
    "Major position detected — POLYGOD scanning for alpha opportunities",
    "Whale activity in Polymarket — POLYGOD computing optimal response",
    "High-volume trade alert — POLYGOD AI evaluating market impact",
]
whale_cycle = itertools.cycle(WHALE_ALERTS)

# Current POLYGOD mode (initialized from settings)
MODE: int = settings.POLYGOD_MODE


async def daily_pnl_report():
    """GOD TIER daily PnL report — runs every 24h"""
    logger.info("=== POLYGOD DAILY PNL REPORT ===")

    # Use your existing PaperMirror (already imported)
    total_pnl = sum(paper.pnls) if paper.pnls else 0.0
    trade_count = len(paper.pnls)

    logger.info(f"Paper PnL: ${total_pnl:.2f} | Trades today: {trade_count}")
    logger.info(f"Current POLYGOD_MODE: {POLYGOD_MODE}")

    # Optional: pull latest market stats from DB
    try:
        from src.backend.polymarket.client import polymarket_client
        top_markets = await polymarket_client.get_top_markets(limit=5)
        logger.info(f"Top 5 markets by volume: {[m.get('title', 'N/A') for m in top_markets]}")
    except Exception as e:
        logger.warning(f"Could not fetch market data for report: {e}")

    # TODO (future): send via email (Resend) or Telegram
    # For now it's logged + visible in Prometheus metrics
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

    # Env vars validation logs with fallbacks (config has defaults)
    logger.info("=== POLYGOD Startup: Environment Validation (main.py) ===")
    logger.info(f"DATABASE_URL={settings.DATABASE_URL!r}")
    logger.info(f"CORS_ORIGINS={settings.CORS_ORIGINS!r}")
    logger.info(f"HOST={settings.HOST!r}, PORT={settings.PORT}, DEBUG={settings.DEBUG}")
    logger.info(f"POLYGOD_MODE={settings.POLYGOD_MODE}, MEM0_CONFIG present={bool(settings.MEM0_CONFIG)}")

    if not settings.NEWS_API_KEY:
        logger.warning("NEWS_API_KEY not set. News aggregation may be disabled.")
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. POLYGOD AI agents disabled.")
    if not settings.TAVILY_API_KEY:
        logger.warning("TAVILY_API_KEY not set. Web search enrichment disabled.")
    if not settings.POLYMARKET_API_KEY:
        logger.info("POLYMARKET_API_KEY not set. Using public Polymarket API only.")
    if not settings.POLYMARKET_SECRET or not settings.POLYMARKET_PASSPHRASE:
        logger.info("POLYMARKET_SECRET / POLYMARKET_PASSPHRASE not fully set. Authenticated trading may be disabled.")

    # Initialize database
    try:
        await init_db()
        logger.info("Database initialized")
    except Exception as e:
        if settings.ALLOW_IN_MEMORY_DB_FALLBACK or settings.DEBUG:
            logger.error(f"Database initialization failed: {e} - Continuing with in-memory fallback")
            settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
            logger.warning("DATABASE_URL overridden to sqlite+aiosqlite:///:memory:")
        else:
            logger.error(f"Database initialization failed: {e}")
            raise

    # Run initial market update with graceful error
    try:
        await update_top_markets()
        logger.info("Initial market data loaded")
    except Exception as e:
        logger.error(f"Failed to load initial market data: {e} - Continuing without market data")
        # Fallback: create empty market data structure, but never crash
        try:
            from src.backend.polymarket.client import create_empty_market_data
            await create_empty_market_data()
            logger.info("Initialized empty market data as fallback.")
        except Exception as inner_e:
            logger.error(f"Failed to initialize empty market data fallback: {inner_e}")

    # Start background scheduler with graceful error handling
    scheduler = get_scheduler()
    try:
        scheduler.start()
        logger.info("Background scheduler started")
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {e} - Continuing without scheduler")
        scheduler = None  # Set to None to avoid shutdown errors

    # Schedule daily PnL report (runs once per day at midnight)
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

    yield

    # Shutdown
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


# Create FastAPI app
app = FastAPI(
    title="POLYGOD API",
    description="POLYGOD - Advanced Polymarket intelligence and trading agent",
    version="0.1.0",
    lifespan=lifespan,
)

# Prometheus metrics — exposes /metrics endpoint
Instrumentator().instrument(app).expose(app)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.websocket("/ws/polygod")
async def polygod_ws(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json({
            "paper_pnl": paper.pnls[-1] if paper.pnls else 0,
            "mode": POLYGOD_MODE,
            "whale_alert": next(whale_cycle)
        })
        await asyncio.sleep(2)


@app.post("/polygod/switch-mode")
async def switch_mode(new_mode: int):
    global POLYGOD_MODE
    POLYGOD_MODE = new_mode
    return {"status": f"Switched to Mode {POLYGOD_MODE} — {'BEAST MODE' if POLYGOD_MODE == 3 else 'safe'}"}


@app.post("/polygod/simulate")
async def monte_carlo_simulate(market_id: str, order_size: float = 1000):
    """GOD TIER simulation dashboard endpoint"""
    from src.backend.polygod_graph import get_enriched_market_data, run_monte_carlo
    
    # Pull latest market data (reuse existing helper)
    market_data = await get_enriched_market_data(market_id)
    sim = run_monte_carlo({"size": order_size}, market_data)  # uses the function from polygod_graph
    
    return {
        "simulation": sim,
        "recommendation": "BEAST APPROVED" if sim["win_prob"] > 0.65 else "SAFE MODE ONLY"
    }


@app.post("/polygod/run")
async def polygod_run(market_id: str, mode: int = 0, question: str = ""):
    """
    GOD TIER CYCLIC SWARM — Full pipeline execution.
    
    Runs the complete POLYGOD pipeline:
    memory_recall → research → x_sentiment → [cyclic debate swarm] → moderator →
    [approve | risk_gate | evolution_lab] → execute → meta_reflection
    
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
        raise HTTPException(status_code=500, detail=f"POLYGOD run failed: {str(e)}")


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
        "service": "POLYGOD API",
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
        log_level="debug" if settings.DEBUG else "info"
    )