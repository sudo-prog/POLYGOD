"""
FastAPI main application entry point.

Configures CORS, routers, and lifespan events for database and background tasks.
"""

import asyncio
import logging
import socket
from contextlib import asynccontextmanager
from datetime import datetime

# Force IPv4 to avoid IPv6 timeouts
old_getaddrinfo = socket.getaddrinfo
def new_getaddrinfo(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]
socket.getaddrinfo = new_getaddrinfo

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.polymarket.client import polymarket_client
from src.backend.news.aggregator import news_aggregator
from src.backend.routes import markets, news, debate, users
from src.backend.tasks.update_markets import get_scheduler, update_top_markets
from src.backend.rag_god_graph import rag_god_app, paper, MODE

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.

    Handles startup and shutdown events.
    """
    logger.info("Starting Polymarket News Tracker API...")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Run initial market update
    try:
        await update_top_markets()
        logger.info("Initial market data loaded")
    except Exception as e:
        logger.error(f"Failed to load initial market data: {e}")

    # Start background scheduler
    scheduler = get_scheduler()
    scheduler.start()
    logger.info("Background scheduler started")

    yield

    # Shutdown
    logger.info("Shutting down...")
    scheduler.shutdown()
    await polymarket_client.close()
    await news_aggregator.close()
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Polymarket News Tracker API",
    description="API for tracking top Polymarket markets with real-time news",
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

# Mount RAG_GOD sub-application
app.mount("/rag-god", rag_god_app)


@app.websocket("/ws/rag-god")
async def rag_god_ws(websocket: WebSocket):
    """WebSocket endpoint for live RAG_GOD stream."""
    await websocket.accept()
    logger.info("[WS] RAG_GOD WebSocket client connected")
    try:
        while True:
            # Get whale alerts (simulated for now)
            whale_alert = "HorizonSplendidView just loaded 150k YES — RAG_GOD analyzing"

            # Send live data
            await websocket.send_json({
                "paper_pnl": paper.pnls[-1] if paper.pnls else 0,
                "paper_stats": paper.get_stats(),
                "mode": MODE,
                "whale_alert": whale_alert,
                "timestamp": datetime.utcnow().isoformat()
            })
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("[WS] RAG_GOD WebSocket client disconnected")
    except Exception as e:
        logger.error(f"[WS] RAG_GOD WebSocket error: {e}")


@app.post("/rag-god/switch-mode")
async def switch_mode(new_mode: int):
    """Switch RAG_GOD risk mode (0-3)."""
    from src.backend.rag_god_graph import MODE as rag_mode

    if new_mode < 0 or new_mode > 3:
        return JSONResponse(
            status_code=400,
            content={"error": "Mode must be between 0 and 3"}
        )

    # Update global MODE
    import src.backend.rag_god_graph as rag_module
    rag_module.MODE = new_mode

    mode_names = {
        0: "OBSERVE",
        1: "CONSERVATIVE",
        2: "MODERATE",
        3: "BEAST MODE"
    }

    logger.info(f"[RAG_GOD] Mode switched to {new_mode} ({mode_names.get(new_mode, 'UNKNOWN')})")

    return {
        "status": f"Mode {new_mode} — {mode_names.get(new_mode, 'UNKNOWN')}",
        "mode": new_mode,
        "mode_name": mode_names.get(new_mode, "UNKNOWN")
    }


@app.get("/api/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "0.1.0",
    }


@app.get("/")
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "name": "Polymarket News Tracker API",
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
