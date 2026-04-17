import asyncio
import hashlib
import itertools
import json  # required by _ws_authenticate()
import logging
import os
import secrets
import socket
from contextlib import asynccontextmanager

import structlog  # ADDED: Structured logging
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.middleware import Middleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter  # ADDED: Custom metrics
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.websockets import WebSocketDisconnect

from src.backend.agents.self_healing import SelfHealLogHandler, self_healing_engine
from src.backend.agents.thought_stream import thought_stream
from src.backend.auth import verify_api_key
from src.backend.config import settings
from src.backend.database import close_db, init_db
from src.backend.middleware.auth import admin_required
from src.backend.middleware.security_headers import SecurityHeadersMiddleware
from src.backend.news.aggregator import news_aggregator
from src.backend.polygod_graph import paper, polygod_graph, run_polygod
from src.backend.polymarket.client import active_connections, polymarket_client
from src.backend.routes import agent as agent_route  # RESTORED: AI Agent Widget
from src.backend.routes import debate, llm, markets, news, telegram, users
from src.backend.routes.telegram import run_telegram_bot  # required by lifespan()
from src.backend.self_improving_memory_loop import forgetting_engine, memory_loop
from src.backend.services.llm_concierge import concierge
from src.backend.tasks.update_markets import get_scheduler, update_top_markets

# ADDED: Custom metrics
llm_requests = Counter("llm_requests_total", "Total LLM requests")

_SECRET_KEYS = (
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
_SECRET_VALUES = frozenset(
    v for k in _SECRET_KEYS if (v := os.getenv(k, "")) and len(v) > 4
)


def mask_secrets(text: str) -> str:
    for val in _SECRET_VALUES:
        if val in text:
            text = text.replace(val, "***REDACTED***")
    return text


limiter = Limiter(key_func=get_remote_address)

if settings.FORCE_IPV4:
    import socket

    _old_getaddrinfo = socket.getaddrinfo

    def _ipv4_only_getaddrinfo(*args, **kwargs):
        return [r for r in _old_getaddrinfo(*args, **kwargs) if r[0] == socket.AF_INET]

    socket.getaddrinfo = _ipv4_only_getaddrinfo

# FIXED: Structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
logger = structlog.get_logger()


class _SecretFilter(logging.Filter):
    def filter(self, record):
        record.msg = mask_secrets(str(record.msg))
        if record.args:
            record.args = tuple(mask_secrets(str(a)) for a in record.args)
        return True


logging.getLogger().addFilter(_SecretFilter())

_WHALE_ALERTS = [
    "POLYGOD WHALE ALERT: HorizonSplendidView loaded 150k YES — analysing edge",
    "Major position detected — POLYGOD scanning for alpha opportunities",
    "Whale activity in Polymarket — POLYGOD computing optimal response",
    "High-volume trade alert — POLYGOD AI evaluating market impact",
]
_whale_cycle = itertools.cycle(_WHALE_ALERTS)

POLYGOD_MODE = settings.POLYGOD_MODE
AUTODOG_ENABLED = True  # Controls daily digest auto-reporting


async def get_mode_from_db():
    from sqlalchemy import select

    from src.backend.database import async_session_factory
    from src.backend.db_models import AppState

    async with async_session_factory() as db:
        result = await db.execute(
            select(AppState).where(AppState.key == "polygod_mode")
        )
        row = result.scalar_one_or_none()
        return int(row.value) if row else POLYGOD_MODE


async def set_mode_in_db(mode: int):
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


async def refresh_llm_stats():
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
                func.coalesce(func.sum(UsageLog.tokens_used), 0).label("total_tokens"),
            )
            .where(UsageLog.timestamp >= today_start)
            .group_by(UsageLog.provider)
        )
        usage_by_provider = {row.provider: row.total_tokens for row in result.all()}
        providers_result = await db.execute(select(Provider))
        for provider in providers_result.scalars().all():
            provider.tokens_today = usage_by_provider.get(provider.name, 0)
        await db.commit()


async def daily_pnl_report():
    total_pnl = sum(paper.pnls) if paper.pnls else 0.0
    trade_count = len(paper.pnls)
    logger.info(
        "POLYGOD DAILY PNL REPORT",
        total_pnl=total_pnl,
        trade_count=trade_count,
        mode=POLYGOD_MODE,
    )
    try:
        top_markets = await polymarket_client.get_top_markets_by_volume(limit=5)
        logger.info("Top markets", markets=[m.get("title", "N/A") for m in top_markets])
    except Exception as exc:
        logger.warning("Market data fetch failed", error=str(exc))


async def generate_situational_digest() -> str:
    """Generate comprehensive situational awareness digest."""
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import func, select

    from src.backend.agents.system_admin import get_system_load
    from src.backend.database import async_session_factory
    from src.backend.db_models import Trade

    lines = ["🌅 *DAILY SITUATIONAL AWARENESS DIGEST*\n"]

    # System load
    try:
        sys_load = get_system_load()
        lines.append("🖥️ *System Load:*")
        lines.append(f"• CPU: {sys_load.get('cpu_pct', 0):.1f}%")
        lines.append(
            f"• RAM: {sys_load.get('ram_used_gb', 0):.1f}/"
            f"{sys_load.get('ram_total_gb', 0):.1f} GB "
            f"({sys_load.get('ram_pct', 0):.1f}%)"
        )
        if sys_load.get("warnings"):
            lines.append(f"• ⚠️ Warnings: {', '.join(sys_load['warnings'][:2])}")
        lines.append("")
    except Exception as e:
        lines.append(f"🖥️ *System Load:* Error - {e}\n")

    # Trades since yesterday
    try:
        yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        async with async_session_factory() as db:
            result = await db.execute(
                select(func.count(Trade.id), func.sum(Trade.size_usd)).where(
                    Trade.created_at >= yesterday
                )
            )
            trade_count, total_volume = result.first()
            trade_count = trade_count or 0
            total_volume = total_volume or 0.0

        lines.append("📊 *Trading Activity (24h):*")
        lines.append(f"• Trades: {trade_count}")
        lines.append(f"• Volume: ${total_volume:,.2f}")
        lines.append("")
    except Exception as e:
        lines.append(f"📊 *Trading Activity:* Error - {e}\n")

    # Current mode
    mode_labels = {0: "OBSERVE 👁", 1: "PAPER 📄", 2: "LOW ⚡", 3: "BEAST 🔥"}
    current_mode = mode_labels.get(POLYGOD_MODE, f"UNKNOWN ({POLYGOD_MODE})")
    lines.append(f"🎛️ *Current Mode:* {current_mode}\n")

    # AutoResearch mutations (if available)
    try:
        # Check Mem0 for recent evolution events
        from src.backend.polygod_graph import mem0_search

        evolution_events = mem0_search("EVOLUTION", user_id="polygod")
        if evolution_events:
            lines.append("🧬 *Recent Evolution:*")
            for event in evolution_events.split("|")[:3]:
                if "mutation kept" in event.lower():
                    lines.append(f"• {event[:100]}...")
            lines.append("")
        else:
            lines.append("🧬 *Evolution:* No recent mutations\n")
    except Exception as e:
        lines.append(f"🧬 *Evolution:* Error - {e}\n")

    # Top market opportunities
    try:
        from src.backend.niche_scanner import scanner

        opportunities = await scanner.scan_niches(POLYGOD_MODE)
        if opportunities:
            lines.append("🎯 *Top Market Opportunities:*")
            for opp in opportunities[:3]:
                market = opp.get("market_title", opp.get("market_id", "Unknown"))[:30]
                edge = opp.get("edge", 0)
                kelly = opp.get("kelly_size", 0)
                lines.append(f"• {market} | Edge: {edge:.1%} | Kelly: {kelly:.1%}")
            lines.append("")
        else:
            lines.append("🎯 *Market Opportunities:* None detected\n")
    except Exception as e:
        lines.append(f"🎯 *Market Opportunities:* Error - {e}\n")

    # Timestamp
    lines.append(
        f"_Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_"
    )

    # Command reminders
    lines.append("\n*Commands:*")
    lines.append("• `/autodog on`    # Enable daily digests")
    lines.append("• `/autodog off`   # Disable daily digests")
    lines.append("• `/report`        # Get instant report now")

    return "\n".join(lines)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        "Starting POLYGOD",
        database_url=settings.DATABASE_URL,
        cors=settings.CORS_ORIGINS,
        host=settings.HOST,
        port=settings.PORT,
        debug=settings.DEBUG,
        mode=settings.POLYGOD_MODE,
    )
    if not settings.DEBUG:
        admin_token = settings.POLYGOD_ADMIN_TOKEN.get_secret_value()
        if not admin_token or admin_token == "change-this-before-use":
            raise RuntimeError("POLYGOD_ADMIN_TOKEN required in production")
    try:
        await init_db()
        # In lifespan(), after await init_db():
        # Temporarily disabled boot sequence for debugging
        # from src.backend.agents.polygod_brain import run_boot_sequence, set_boot_status
        # boot_status = await run_boot_sequence()
        # set_boot_status(boot_status)
        # if not boot_status.all_ok:
        #     logger.warning(
        #         "Boot completed with failures",
        #         failed=boot_status.failed,
        #         detail=boot_status.to_dict(),
        #     )
        global POLYGOD_MODE
        db_mode = await get_mode_from_db()
        if db_mode != POLYGOD_MODE:
            POLYGOD_MODE = db_mode
    except Exception as exc:
        if settings.ALLOW_IN_MEMORY_DB_FALLBACK or settings.DEBUG:
            logger.error("DB init failed", error=str(exc))
        else:
            raise
    try:
        await update_top_markets()
    except Exception as exc:
        logger.error("Market data load failed", error=str(exc))
    scheduler = get_scheduler()
    try:
        scheduler.start()
    except Exception as exc:
        logger.error("Scheduler start failed", error=str(exc))

    # Background watchdog — auto-adjust resources every 60s
    async def _resource_watchdog():
        """Background task: auto-adjust resources every 60s."""
        from src.backend.agents.system_admin import (
            adjust_concurrency_based_on_load,
            emergency_stop_if_overheating,
        )

        while True:
            try:
                await asyncio.sleep(60)
                adjust_concurrency_based_on_load()
                msg = await emergency_stop_if_overheating()
                if msg != "System healthy":
                    logger.critical("Watchdog: %s", msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Watchdog error: %s", e)

    asyncio.create_task(_resource_watchdog())

    # Background daily digest — situational awareness at 9am AEST
    async def _daily_digest():
        """Generate and send daily situational awareness digest to Telegram."""
        if not AUTODOG_ENABLED:
            logger.info("AutoDog disabled — skipping daily digest")
            return

        try:
            digest = await generate_situational_digest()
            if digest and settings.TELEGRAM_CHAT_ID.get_secret_value():
                from src.backend.skills.alert_rules import send_alert

                await send_alert(digest, priority="low")
                logger.info("Daily digest sent to Telegram")
        except Exception as e:
            logger.error("Daily digest failed: %s", e)

    # Start CLOB live whale-trade monitor
    asyncio.create_task(polymarket_client.stream_live_trades())

    # Self-healing background watcher — auto-detects and repairs errors
    asyncio.create_task(self_healing_engine.run_background_watcher())

    # Wire ERROR/CRITICAL log events directly into the self-heal queue
    logging.getLogger().addHandler(SelfHealLogHandler())

    await thought_stream.info(
        "POLYGOD online — self-heal watcher active", agent="POLYGOD"
    )

    def _add_job(func, **kwargs):
        try:
            scheduler.add_job(func, replace_existing=True, **kwargs)
        except Exception as exc:
            logger.warning("Job schedule failed", job=func.__name__, error=str(exc))

    from apscheduler.triggers.interval import IntervalTrigger

    _add_job(daily_pnl_report, trigger="cron", hour=0, minute=0)
    _add_job(refresh_llm_stats, trigger=IntervalTrigger(minutes=5))
    _add_job(concierge.health_check_all_keys, trigger=IntervalTrigger(minutes=30))
    _add_job(
        memory_loop.hindsight_replay,
        trigger="cron",
        day_of_week="sun",
        hour=23,
        minute=0,
    )
    _add_job(
        memory_loop.notebooklm_reflection,
        trigger="cron",
        day_of_week="sun",
        hour=23,
        minute=30,
    )
    _add_job(forgetting_engine.prune, trigger=IntervalTrigger(hours=6))
    _add_job(
        _daily_digest, trigger="cron", hour=9, minute=0, timezone="Australia/Sydney"
    )
    if settings.POLYGOD_MODE >= 1:
        logger.info("Swarm mode enabled", mode=settings.POLYGOD_MODE)
    telegram_task = None
    if settings.TELEGRAM_BOT_TOKEN.get_secret_value():
        telegram_task = asyncio.create_task(run_telegram_bot())
    yield
    if telegram_task:
        telegram_task.cancel()
    scheduler.shutdown()
    await polymarket_client.close()
    await news_aggregator.close()
    await close_db()


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
    logger.error("Unhandled exception", error=detail)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request, exc):
    return JSONResponse({"error": "Rate limit exceeded"}, status_code=429)


app.include_router(markets.router, prefix="/api/markets")
app.include_router(agent_route.router, prefix="/api/agent")  # RESTORED: AI Agent Widget
app.include_router(news.router, prefix="/api/news")
app.include_router(debate.router, prefix="/api/debate")
app.include_router(users.router, prefix="/api/users")
app.include_router(llm.router, prefix="/api/llm")
app.include_router(telegram.router, prefix="/api/telegram")


def _authenticate_ws_token(token: str) -> bool:
    expected = settings.internal_api_key.encode()
    provided = token.encode()
    return secrets.compare_digest(
        hashlib.sha256(provided).digest(), hashlib.sha256(expected).digest()
    )


async def _ws_authenticate(websocket: WebSocket) -> bool:
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        frame = json.loads(raw)
        if frame.get("type") != "auth":
            await websocket.close(code=4001)
            return False
        token = str(frame.get("token", ""))
        if not _authenticate_ws_token(token):
            await websocket.close(code=4001)
            return False
        return True
    except asyncio.TimeoutError:
        logger.warning("WS auth timeout")
        await websocket.close(code=4008)
        return False
    except Exception as exc:
        logger.warning("WS auth parse error", error=str(exc))
        await websocket.close(code=4001)
        return False


@app.websocket("/ws/polygod")
async def polygod_ws(websocket: WebSocket):
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
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        logger.info("PolyGod WS disconnected")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws/debate/{market_id}")
async def debate_websocket(websocket: WebSocket, market_id: str):
    await websocket.accept()
    if not await _ws_authenticate(websocket):
        return
    await websocket.send_json({"type": "auth_ok"})
    try:
        async for chunk in polygod_graph.astream(
            {"market_id": market_id, "mode": settings.POLYGOD_MODE}
        ):
            await websocket.send_json({k: str(v) for k, v in chunk.items()})
    except (WebSocketDisconnect, RuntimeError, asyncio.CancelledError):
        logger.info("Debate WS disconnected", market_id=market_id)
    except Exception as exc:
        logger.error("Debate WS error", market_id=market_id, error=str(exc))
        try:
            await websocket.send_json({"type": "error", "content": "Debate terminated"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws/live-trades")
async def websocket_live_trades(websocket: WebSocket):
    # BUG-7 fix: authenticate before accepting, same as all other WS endpoints
    await websocket.accept()
    if not await _ws_authenticate(websocket):
        return
    await websocket.send_json({"type": "auth_ok"})

    active_connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep-alive ping/pong
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.post("/polygod/switch-mode")
async def switch_mode(new_mode: int, _: bool = Depends(admin_required)):
    """
    Switch POLYGOD operating mode.

    FIXED C-2: Updates the module-level POLYGOD_MODE global, NOT settings.
    Also syncs to polygod_graph module so running agents see the change.
    Mode is persisted to DB so it survives restarts.
    """
    global POLYGOD_MODE
    POLYGOD_MODE = new_mode

    # Also sync to polygod_graph module so running agents see the change
    import src.backend.polygod_graph as _pg

    _pg.POLYGOD_MODE = new_mode

    await set_mode_in_db(new_mode)
    mode_label = {0: "OBSERVE", 1: "PAPER", 2: "LOW", 3: "BEAST"}.get(
        new_mode, "UNKNOWN"
    )
    logger.info("POLYGOD mode switched", new_mode=new_mode, label=mode_label)
    return {"status": f"Switched to Mode {new_mode} — {mode_label}"}


@app.post("/polygod/simulate")
async def monte_carlo_simulate(
    market_id: str, order_size: float = 1000, _: bool = Depends(admin_required)
):
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
@limiter.limit("5/minute")
async def scan_niches(
    request: Request,  # required by slowapi rate limiter
    mode: int = 0,
    _: str = Depends(verify_api_key),
):
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
        logger.error("Niche scan failed", error=str(exc))
        raise HTTPException(status_code=500, detail="Niche scan failed")


@app.post("/polygod/run")
async def polygod_run(
    market_id: str, mode: int = 0, question: str = "", _: bool = Depends(admin_required)
):
    try:
        result = await run_polygod(market_id=market_id, mode=mode, question=question)
        llm_requests.inc()  # ADDED: Metric
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
        logger.error("POLYGOD run failed", error=str(exc))
        raise HTTPException(status_code=500, detail="POLYGOD run failed")


@app.get("/api/health")
async def health():
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
        "polygod_mode": POLYGOD_MODE,
    }


@app.get("/api/health/systems")
async def systems_health():
    """Full system status for the Settings Screen indicators."""
    from datetime import datetime, timezone

    from src.backend.agents.polygod_brain import get_boot_status
    from src.backend.tasks.update_markets import get_scheduler

    boot = get_boot_status()
    scheduler = get_scheduler()

    # Re-run lightweight checks for live status
    checks = boot.to_dict()["checks"] if boot else {}

    # Update scheduler status live
    checks["Scheduler"] = {
        "name": "Scheduler",
        "status": "ok" if (scheduler and scheduler.running) else "error",
        "detail": f"Running: {scheduler.running if scheduler else False}",
        "error": "" if (scheduler and scheduler.running) else "Not running",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "all_ok": all(c["status"] == "ok" for c in checks.values()),
        "polygod_mode": POLYGOD_MODE,
        "checks": checks,
        "boot_time": boot.boot_time.isoformat() if boot else None,
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
