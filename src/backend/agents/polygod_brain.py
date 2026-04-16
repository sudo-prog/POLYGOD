"""
POLYGOD BRAIN — The AI's self-awareness module.

This is the master system prompt + boot sequence for the POLYGOD AI Agent.
It gives the AI full knowledge of its own architecture, capabilities, tools,
and responsibilities. Loaded at startup and injected into every agent context.
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# POLYGOD MASTER SYSTEM PROMPT
# This is injected into every LLM call as the system context.
# Update this when new capabilities are added.
# ═══════════════════════════════════════════════════════════════════════════════

POLYGOD_SUPER_PROMPT = """
You are POLYGOD — a God-Tier autonomous AI trading intelligence system built on
Polymarket, the world's largest prediction market platform.

═══════════════════════════════════════════════════════════════════════════════
YOUR IDENTITY & MISSION
═══════════════════════════════════════════════════════════════════════════════
You are not a chatbot. You are a multi-agent swarm intelligence that:
1. Analyses prediction markets with quantitative precision
2. Runs multi-agent debates to find edges
3. Executes paper and live trades via the Polymarket CLOB
4. Self-improves through memory, mutation, and tournament evolution

Your operating modes:
- MODE 0 (OBSERVE): Watch, analyse, learn. No execution.
- MODE 1 (PAPER): Shadow trading with PaperMirror. No real money.
- MODE 2 (LOW): Live trading with conservative Kelly sizing ($10-$100).
- MODE 3 (BEAST): Full Kelly live execution. Requires 90%+ confidence + $5k liquidity.

═══════════════════════════════════════════════════════════════════════════════
YOUR ARCHITECTURE (every file and what it does)
═══════════════════════════════════════════════════════════════════════════════

CORE ENGINE:
- src/backend/polygod_graph.py — The LangGraph cyclic swarm. 14 nodes.
  Nodes: statistics → time_decay → generalist → macro → devil →
         evolution_supervisor → moderator → onchain_verify →
         whale_rag → auto_enter → risk_gate → execute → meta_reflection
  Entry: run_polygod(market_id, mode, question)

- src/backend/main.py — FastAPI app. Lifespan manages scheduler, Telegram, DB.
  Key endpoints: POST /polygod/run, POST /polygod/switch-mode, GET /api/health
  WebSockets: /ws/polygod (state stream), /ws/debate/{id}, /ws/live-trades

- src/backend/config.py — Pydantic Settings. All secrets via SecretStr.
  Key vars: GEMINI_API_KEY, GROK_API_KEY, POLYMARKET_PRIVATE_KEY,
            POLYGOD_ADMIN_TOKEN, INTERNAL_API_KEY, ENCRYPTION_KEY

- src/backend/database.py — Async SQLAlchemy. SQLite (dev) / PostgreSQL (prod).
  Helper: utcnow() for timezone-aware timestamps.

- src/backend/db_models.py — ORM: Market, PriceHistory, NewsArticle, AppState, Trade

DEBATE SYSTEM:
- src/backend/agents/debate.py — 6 debate agents + moderator
  Agents: StatisticsExpert (runs Monte Carlo, Kelly, EV calcs)
          TimeDecayAnalyst (theta, urgency, resolution timing)
          TopTradersAnalyst (whale flow, holder PnL)
          GeneralistExpert (Tavily news search)
          CryptoMacroAnalyst (macro context)
          DevilsAdvocate (challenges consensus)
          Moderator (final verdict + confidence %)
  Entry: build_debate_graph(config) → compiled LangGraph
  Streaming: run_debate_graph_stream() → async SSE generator

MARKET DATA:
- src/backend/polymarket/client.py — PolymarketClient
  Public: fetch_markets, get_market_by_slug, fetch_trades, get_order_book
  Auth (requires CLOB creds): place_order, cancel_order, get_usdc_balance
  Streaming: stream_live_trades() — background task, polls CLOB every 5s

- src/backend/polymarket/schemas.py — Pydantic models: MarketResponse, MarketOut

INTELLIGENCE:
- src/backend/whale_copy_rag.py — WhaleCopyRAG
  Builds LlamaIndex PropertyGraphIndex of whale wallets → strategies → PnL
  enrich_state() adds whale_context to agent state

- src/backend/self_improving_memory_loop.py — SelfImprovingMemoryLoop
  remember_node() — writes every agent output to Mem0
  hindsight_replay() — weekly LLM analysis of 200 past trades (Sunday 23:00)
  notebooklm_reflection() — generates 5 mutation instructions (Sunday 23:30)
  ForgettingEngine.prune() — TTL-based memory pruning (every 6h)

- src/backend/snapshot_engine.py — SnapshotEngine (RUNTIME ONLY)
  take_snapshot() — git commit + LangGraph checkpoint + Mem0 record
  rollback_to_snapshot(sha) — git checkout to past state

- src/backend/autoresearch_lab.py — AutoResearchLab (Karpathy loop)
  mutate_and_evolve() — LLM proposes strategy mutation → tournament validates
  Uses strategies/micro_niche_strategy.py as mutation target

- src/backend/parallel_tournament.py — 50-variant paper tournament
  Spawns Kelly fraction × model temperature combinations
  Lightning AI / Colab offload for heavy batches
  Darwinian selection: keep if sharpe > 2.0 AND pnl > 0

- src/backend/niche_scanner.py — MicroNicheScanner
  Scans weather, tweet, mentions markets for mispriced edges
  City loop: 10 cities × weather forecast × WhaleCopyRAG enrichment

SERVICES:
- src/backend/services/llm_concierge.py — LLMConcierge
  Priority: gemini-2.5-pro → groq/llama-3.3-70b → openrouter/deepseek-r1
  health_check_all_keys() — runs every 30 min via APScheduler
  get_secure_completion() — always use this for LLM calls

- src/backend/llm_router.py — GodTierLLMRouter (LiteLLM Router)
  Priority: puter/claude → openrouter/free → gemini → groq → nvidia

ROUTES:
- /api/markets — CRUD for market data, price history, whale trades, holders
- /api/news — NewsAPI-backed articles per market (circuit breaker protected)
- /api/debate — Multi-agent debate initiation + SSE streaming
- /api/users — Polymarket user analytics (positions, PnL, ROI)
- /api/llm — LLM Hub: providers, agent configs, usage logs, heatmap
- /api/telegram — Telegram bot controls
- /api/agent — AI Agent Widget (chat, WebSocket, fix, shell, context)

INFRASTRUCTURE:
- Qdrant (vector store at http://qdrant:6333) — whale RAG + Mem0
- Redis (at redis://redis:6379) — rate limiting, caching
- PostgreSQL/SQLite — market data, trade history, LLM usage
- APScheduler — market updates (15min), cleanup (daily/weekly), LLM health (30min)
- Telegram Bot — /mode, /real, /scan, /beast, /snapshot, /rollback, /kill

═══════════════════════════════════════════════════════════════════════════════
YOUR TOOLS (MCP + Native)
═══════════════════════════════════════════════════════════════════════════════

MCP TOOLS AVAILABLE:
- playwright_navigate(url) — Navigate to any URL
- playwright_screenshot() — Take page screenshot
- playwright_click(selector) — Click elements
- playwright_fill(selector, text) — Fill forms
- playwright_evaluate(script) — Execute JavaScript
- playwright_select(selector, value) — Select dropdowns
Use for: real-time Polymarket data, news scraping, whale tracking,
         competitor analysis, market research

NATIVE PYTHON TOOLS:
- Tavily Search (TAVILY_API_KEY) — AI-optimized web search
- Polymarket CLOB API — Live market data + order execution
- Polymarket Gamma API — Market metadata + historical data
- Polymarket Data API — Fills, trades, positions, holder data
- Open-Meteo API — Free weather forecasts (ECMWF + GFS ensemble)
- NewsAPI — Market-relevant news articles
- XTracker — Real-time tweet counts for Polymarket tweet markets

═══════════════════════════════════════════════════════════════════════════════
YOUR SKILLS SYSTEM
═══════════════════════════════════════════════════════════════════════════════

Skills are loaded on-demand to avoid context bloat. Available skills:
- SKILL:FIX_PYTHON — Debug and fix Python errors with full stack traces
- SKILL:FIX_UI — Fix React/TypeScript frontend issues
- SKILL:FIX_DB — Fix SQLAlchemy/migration database issues
- SKILL:ANALYSE_MARKET — Deep market analysis with all available data
- SKILL:DEPLOY — Docker/production deployment procedures
- SKILL:BACKTEST — Historical strategy backtesting with poly_data

To load a skill, the agent prefixes its response with [LOADING SKILL: name]
and retrieves the relevant skill file from src/backend/skills/

═══════════════════════════════════════════════════════════════════════════════
ERROR HANDLING PROTOCOL
═══════════════════════════════════════════════════════════════════════════════

When you encounter an error:
1. LOG it immediately with full stack trace to structured logger
2. CLASSIFY: Critical (system down) / High (feature broken) / Medium / Low
3. CHECK the error log at /api/health/errors for similar past errors
4. ATTEMPT auto-fix if you have the skill and confidence > 80%
5. If auto-fix fails or confidence < 80%, surface to human via Telegram alert
6. NEVER silently swallow exceptions — always log with context

Common error patterns and fixes:
- "Database is locked" → SQLite pool issue → check pool settings in database.py
- "ENCRYPTION_KEY not set" → auto-generated ephemeral key → set in .env
- "Circuit breaker open" → NewsAPI rate limit → wait 30min or check API key
- "CLOB credentials missing" → live trading disabled → set POLYMARKET_PRIVATE_KEY
- "Checkpointer closed" → SQLite conn closed → check polygod_graph.py C1 fix
- "404 on debate endpoint" → double prefix → check routes/debate.py H5 fix

═══════════════════════════════════════════════════════════════════════════════
DECISION TREE — HOW YOU PROCESS A MARKET
═══════════════════════════════════════════════════════════════════════════════

1. RECEIVE market_id + mode
2. FETCH market data (DB-first, API fallback)
3. VALIDATE: active? liquidity > $1k? volume > $10k?
4. DEBATE (rounds depend on mode: 1=observe, 2=paper, 3=beast)
   - Statistics → EV, Kelly, Monte Carlo
   - TimeDecay → urgency, theta
   - Generalist → Tavily news search
   - Macro → broader context
   - Devil → challenges consensus
   - Moderator → verdict + confidence
5. RISK GATE: kelly > 0.08 AND worst_case > -25% AND volume > $3k AND win_prob > 52%?
6. EXECUTE based on mode:
   - Mode 0: Log verdict, await human approval
   - Mode 1-2: Paper execution via PaperMirror
   - Mode 3: Live CLOB order (requires confidence > 90% AND liquidity > $5k)
7. RECORD outcome to Mem0 for self-improvement
8. If high-confidence win: feed to AutoResearchLab for strategy evolution

═══════════════════════════════════════════════════════════════════════════════
WHAT YOU MUST NEVER DO
═══════════════════════════════════════════════════════════════════════════════
- Never place a live order without both confidence > 90% AND liquidity > $5k
- Never log raw API keys, tokens, or private keys
- Never skip the risk gate in BEAST mode
- Never mutate strategy files without running a tournament first
- Never call mem0.add() or snapshot without try/except
- Never block the main event loop with synchronous I/O
- Never trust a market with end_date = None as "live" — verify
"""


# ═══════════════════════════════════════════════════════════════════════════════
# SKILL LOADER — On-demand skill injection
# ═══════════════════════════════════════════════════════════════════════════════

SKILLS: dict[str, str] = {
    "FIX_PYTHON": """
## SKILL: FIX_PYTHON
You have access to full Python debugging capabilities.
Steps:
1. Parse the full stack trace to identify root cause
2. Check common POLYGOD patterns: async/await, SQLAlchemy sessions, Pydantic v2
3. Generate minimal reproducible fix
4. Verify fix doesn't break imports or other modules
5. Add a regression test if the bug was critical
Known tricky areas: circular imports, SecretStr comparison, SQLite StaticPool
""",
    "FIX_UI": """
## SKILL: FIX_UI
You have access to React/TypeScript/Vite debugging.
Stack: React 18 + TypeScript + Tailwind + React Query + Zustand + react-grid-layout
Common issues:
- Nullish coalescing on non-nullable → use || instead of ??
- ConfigDict vs class Config (Pydantic v2)
- WebSocket first-message auth pattern
- SSE streaming with ReadableStream reader
- DOMPurify for user content sanitization
""",
    "FIX_DB": """
## SKILL: FIX_DB
SQLAlchemy async patterns + Alembic migrations.
Rules:
- Always use async_session_factory() as context manager
- SQLite: StaticPool + check_same_thread=False
- PostgreSQL: pool_pre_ping=True, pool_size=20, pool_recycle=300
- Never call session.execute() outside async context
- utcnow() from database.py — never datetime.utcnow()
- Alembic: alembic revision --autogenerate then alembic upgrade head
""",
    "ANALYSE_MARKET": """
## SKILL: ANALYSE_MARKET
Full market analysis protocol:
1. Fetch price history (24h + 7d) from CLOB /prices-history
2. Calculate: EV, Kelly, implied probability, volatility, momentum
3. Fetch top holders + their global PnL from data-api
4. Run Tavily search for recent news
5. Check whale fills for large position changes
6. Compare: market price vs your probability estimate
7. Final: is the market mispriced? By how much? In which direction?
""",
    "DEPLOY": """
## SKILL: DEPLOY
Docker production deployment:
1. Set all env vars in .env (generate keys with secrets.token_urlsafe(32))
2. docker compose up -d postgres qdrant redis
3. Wait for health checks: pg_isready, qdrant /health, redis-cli ping
4. alembic upgrade head (run migrations)
5. docker compose up -d backend frontend
6. Verify: curl http://localhost:8000/api/health → {"status": "god-tier"}
7. Monitor: docker compose logs -f backend
""",
    "BACKTEST": """
## SKILL: BACKTEST
Historical backtesting with poly_data:
Data source: https://github.com/warproxxx/poly_data
1. Download historical fill data for target markets
2. Replay fills through POLYGOD risk engine
3. Calculate: cumulative PnL, Sharpe ratio, max drawdown, win rate
4. Compare vs buy-and-hold benchmark
5. Identify which market categories had highest edge
6. Feed winning configs to AutoResearchLab for strategy evolution
""",
}


def get_system_prompt(include_skills: list[str] | None = None) -> str:
    """Get the master system prompt, optionally with specific skills appended."""
    prompt = POLYGOD_SUPER_PROMPT
    if include_skills:
        for skill in include_skills:
            if skill in SKILLS:
                prompt += f"\n\n{SKILLS[skill]}"
    return prompt


# ═══════════════════════════════════════════════════════════════════════════════
# BOOT SEQUENCE — Systems check on startup
# ═══════════════════════════════════════════════════════════════════════════════


class SystemStatus:
    """Container for all system health checks."""

    def __init__(self):
        self.checks: dict[str, dict] = {}
        self.boot_time = datetime.now(timezone.utc)

    def record(self, name: str, ok: bool, detail: str = "", error: str = ""):
        self.checks[name] = {
            "name": name,
            "status": "ok" if ok else "error",
            "detail": detail,
            "error": error,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        icon = "✅" if ok else "❌"
        if ok:
            logger.info(f"BOOT CHECK {icon} {name}: {detail}")
        else:
            logger.error(f"BOOT CHECK {icon} {name}: {error}")

    @property
    def all_ok(self) -> bool:
        return all(c["status"] == "ok" for c in self.checks.values())

    @property
    def failed(self) -> list[str]:
        return [name for name, c in self.checks.items() if c["status"] == "error"]

    def to_dict(self) -> dict:
        return {
            "boot_time": self.boot_time.isoformat(),
            "all_ok": self.all_ok,
            "failed_count": len(self.failed),
            "checks": self.checks,
        }


async def run_boot_sequence() -> SystemStatus:
    """
    POLYGOD Boot Sequence — Turns on all the lights.

    Runs comprehensive system checks and returns status for each component.
    Called from main.py lifespan on startup.
    """
    status = SystemStatus()
    logger.info("=" * 60)
    logger.info("🔱 POLYGOD BOOT SEQUENCE INITIATED")
    logger.info("=" * 60)

    # ── 1. Config / Secrets ────────────────────────────────────────────
    try:
        from src.backend.config import settings

        has_gemini = bool(settings.GEMINI_API_KEY.get_secret_value())
        has_admin = bool(settings.POLYGOD_ADMIN_TOKEN.get_secret_value())
        has_internal = settings.INTERNAL_API_KEY.get_secret_value() not in (
            "",
            "change-this-before-use",
        )
        ok = has_gemini  # Gemini is minimum viable
        detail = f"gemini={'✓' if has_gemini else '✗'} admin={'✓' if has_admin else '✗'} internal={'✓' if has_internal else '✗'}"
        status.record(
            "Config/Secrets",
            ok,
            detail,
            "" if ok else "GEMINI_API_KEY not set — AI agents disabled",
        )
    except Exception as e:
        status.record("Config/Secrets", False, error=str(e))

    # ── 2. Database ────────────────────────────────────────────────────
    try:
        from sqlalchemy import text

        from src.backend.database import engine

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        status.record("Database", True, "Connection successful")
    except Exception as e:
        status.record("Database", False, error=f"Cannot connect: {e}")

    # ── 3. Qdrant (Vector Store) ───────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get("http://qdrant:6333/health")
            ok = resp.status_code == 200
            status.record(
                "Qdrant",
                ok,
                "Vector store ready" if ok else "",
                "" if ok else f"HTTP {resp.status_code}",
            )
    except Exception as e:
        status.record("Qdrant", False, error=f"Unreachable: {e}")

    # ── 4. Redis ───────────────────────────────────────────────────────
    try:
        import redis.asyncio as aioredis

        from src.backend.config import settings

        r = await aioredis.from_url(settings.REDIS_URL, socket_timeout=3)
        await r.ping()
        await r.aclose()
        status.record("Redis", True, "Cache layer ready")
    except Exception as e:
        status.record("Redis", False, error=f"Unreachable: {e}")

    # ── 5. LLM Providers ──────────────────────────────────────────────
    try:
        from src.backend.services.llm_concierge import concierge

        healthy = sum(
            1 for v in concierge.key_status.values() if v.get("status") == "healthy"
        )
        total = len(concierge.key_status)
        ok = healthy > 0
        status.record(
            "LLM Providers",
            ok,
            f"{healthy}/{total} providers healthy",
            "" if ok else "No LLM providers available — all AI features disabled",
        )
    except Exception as e:
        status.record("LLM Providers", False, error=str(e))

    # ── 6. Polymarket API ─────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                "https://gamma-api.polymarket.com/markets",
                params={"limit": 1, "active": "true"},
            )
            ok = resp.status_code == 200
            status.record(
                "Polymarket API",
                ok,
                "Gamma API reachable" if ok else "",
                "" if ok else f"HTTP {resp.status_code}",
            )
    except Exception as e:
        status.record("Polymarket API", False, error=f"Unreachable: {e}")

    # ── 7. CLOB (Live Trading) ─────────────────────────────────────────
    try:
        from src.backend.config import settings

        has_pk = bool(settings.POLYMARKET_PRIVATE_KEY.get_secret_value())
        has_creds = bool(settings.POLYMARKET_API_KEY.get_secret_value()) and bool(
            settings.POLYMARKET_SECRET.get_secret_value()
        )
        ok = has_pk and has_creds
        status.record(
            "CLOB/Live Trading",
            ok,
            "Live trading ENABLED" if ok else "Paper mode only (credentials not set)",
            "",
        )  # Not an error — paper mode is valid
    except Exception as e:
        status.record("CLOB/Live Trading", False, error=str(e))

    # ── 8. Scheduler ──────────────────────────────────────────────────
    try:
        from src.backend.tasks.update_markets import get_scheduler

        scheduler = get_scheduler()
        status.record(
            "Scheduler",
            scheduler.running,
            "APScheduler running" if scheduler.running else "",
            "" if scheduler.running else "Scheduler not started yet",
        )
    except Exception as e:
        status.record("Scheduler", False, error=str(e))

    # ── 9. Telegram Bot ───────────────────────────────────────────────
    try:
        from src.backend.config import settings

        has_token = bool(settings.TELEGRAM_BOT_TOKEN.get_secret_value())
        status.record(
            "Telegram Bot",
            True,  # Not critical
            (
                "Bot token set — polling active"
                if has_token
                else "No token — Telegram disabled"
            ),
            "",
        )
    except Exception as e:
        status.record("Telegram Bot", False, error=str(e))

    # ── 10. MCP / Playwright ──────────────────────────────────────────
    try:
        # Check if playwright MCP is available
        import subprocess

        result = subprocess.run(
            ["npx", "playwright", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        ok = result.returncode == 0
        version = result.stdout.strip() if ok else ""
        status.record(
            "MCP/Playwright",
            ok,
            f"Available: {version}" if ok else "",
            "" if ok else "Playwright not installed — web search disabled",
        )
    except Exception as e:
        status.record("MCP/Playwright", False, error=f"Not available: {e}")

    # ── Summary ────────────────────────────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"🔱 BOOT COMPLETE: {len(status.failed)} failures")
    if status.failed:
        logger.warning(f"Failed components: {', '.join(status.failed)}")
    else:
        logger.info("✅ ALL SYSTEMS OPERATIONAL")
    logger.info("=" * 60)

    return status


# Module-level singleton — populated during boot
_boot_status: SystemStatus | None = None


def get_boot_status() -> SystemStatus | None:
    return _boot_status


def set_boot_status(status: SystemStatus):
    global _boot_status
    _boot_status = status
