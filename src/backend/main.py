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
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.news.aggregator import news_aggregator
from src.backend.polygod_graph import paper, polygod_app
from src.backend.polymarket.client import polymarket_client
from src.backend.routes import debate, markets, news, users
from src.backend.tasks.update_markets import get_scheduler, update_top_markets

# Force IPv4 to avoid IPv6 timeouts (helps in some Docker/network setups)
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

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
        logger.error(f"Database initialization failed: {e} - Continuing with in-memory fallback")
        settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
        logger.warning("DATABASE_URL overridden to sqlite+aiosqlite:///:memory:")

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

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(markets.router)
app.include_router(news.router)
app.include_router(debate.router)
app.include_router(users.router)

# Mount POLYGOD sub-application
app.mount("/polygod", polygod_app, name="polygod")


@app.websocket("/ws/polygod")
async def polygod_ws(websocket: WebSocket):
    """WebSocket streaming POLYGOD status to the frontend."""
    await websocket.accept()
    while True:
        await websocket.send_json(
            {
                "paper_pnl": paper.pnls[-1] if paper.pnls else 0,
                "mode": MODE,
                "whale_alert": next(whale_cycle),
            }
        )
        await asyncio.sleep(2)


@app.post("/polygod/switch-mode")
async def switch_mode(new_mode: int):
    """Switch POLYGOD operating mode (1=analysis, 2=safe, 3=beast)."""
    if new_mode not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail="Mode must be 1, 2, or 3")
    global MODE
    MODE = new_mode
    mode_names = {1: "ANALYSIS MODE", 2: "SAFE MODE", 3: "BEAST MODE"}
    return {"status": f"Switched to POLYGOD MODE {MODE} — {mode_names[MODE]}"}


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
    )
