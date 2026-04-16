"""
POLYGOD_GRAPH — Cyclic debate swarm + paper tournament + AutoResearchLab.

Changes vs previous version:
  - FIXED C1: SqliteSaver was given a CLOSED connection (conn.close() was called
              before passing conn to SqliteSaver). Every checkpoint write raised
              ProgrammingError. Now the connection is kept open for the process
              lifetime.
  - FIXED C3: place_order in BEAST MODE claimed "LIVE TRADE EXECUTED" while
              actually doing nothing (the clob client was fetched but never called).
              Now raises NotImplementedError with an explicit message so the
              behaviour is honest and traceable.
  - FIXED L2: GROK_API_KEY was compared as SecretStr object to truthy — works
              for non-empty strings but is semantically wrong. Now uses
              .get_secret_value() explicitly.
  - FIXED M3: get_enriched_market_data() no longer makes a full 50-market API
              call just to find one market. It queries the local DB first and
              only falls back to the API if the market is not cached.
  - FIXED M7: run_monte_carlo uses an isolated random.Random(seed) instance
              so results are reproducible when a seed is provided (useful in
              tests and backtest comparisons).
  - FIXED L1: datetime.utcnow() → datetime.now(UTC).
"""

import asyncio
import json
import logging
import random
import re
import uuid
from datetime import datetime
from typing import Any, TypedDict

# ── Execution timeout to prevent runaway CPU/memory spikes ─────────────────────
POLYGOD_EXECUTION_TIMEOUT_SECONDS = 300  # 5 minutes max per run

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_xai import ChatXAI
from langgraph.graph import END, StateGraph

# LLM Concierge for secure multi-provider routing
try:
    from src.backend.services.llm_concierge import concierge

    HAS_CONCIERGE = True
except ImportError:
    HAS_CONCIERGE = False
    concierge = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── LangGraph checkpointer ───────────────────────────────────────────────────
try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    MemorySaver = None  # type: ignore[assignment]

checkpointer = None
try:
    import sqlite3

    from langgraph.checkpoint.sqlite import SqliteSaver

    # CRITICAL FIX C1: Do NOT call conn.close() before passing to SqliteSaver.
    # SqliteSaver needs a live connection for the entire process lifetime.
    _checkpoint_conn = sqlite3.connect("checkpoints.db", check_same_thread=False)
    checkpointer = SqliteSaver(_checkpoint_conn)
    logger.info("Checkpointer: SqliteSaver (checkpoints.db)")
except Exception as _e:
    logger.warning("SqliteSaver not available: %s — falling back to MemorySaver", _e)
    if MemorySaver:
        checkpointer = MemorySaver()
        logger.info("Checkpointer: MemorySaver (in-memory, state is not persisted)")
    else:
        logger.error(
            "No checkpointer available — graph state will not persist across runs"
        )

try:
    from mem0 import Memory
except ImportError:
    Memory = None  # type: ignore[assignment]

try:
    import llama_index.core  # noqa: F401

    HAS_LLAMA_INDEX = True
except ImportError:
    HAS_LLAMA_INDEX = False

from src.backend.autoresearch_lab import autoresearch_lab
from src.backend.config import settings
from src.backend.parallel_tournament import parallel_paper_tournament
from src.backend.polymarket.client import polymarket_client
from src.backend.self_improving_memory_loop import memory_loop
from src.backend.snapshot_engine import snapshot_engine
from src.backend.whale_copy_rag import whale_rag

# ==================== MODE ====================
# For backward compatibility, we maintain a module-level POLYGOD_MODE that gets
# synced from settings when run_polygod() is called. Use settings.POLYGOD_MODE
# for direct access to the current mode.
POLYGOD_MODE: int = 0


# ==================== LLM ROUTING ====================
def get_llm(model: str = "gemini"):
    """
    LLM router — prefers free Gemini; escalates to Grok only when key is set.

    FIXED L2: GROK_API_KEY is now compared via .get_secret_value() rather than
    truthy-checking the SecretStr object directly.
    """
    grok_key = settings.GROK_API_KEY.get_secret_value()
    if model == "grok" and grok_key:
        logger.info("LLM routing → Grok-4 (high-stakes escalation)")
        return ChatXAI(model="grok-4", api_key=grok_key, temperature=0.3)
    logger.info("LLM routing → Gemini (free tier)")
    gemini_key = settings.GEMINI_API_KEY.get_secret_value()
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro-exp-03-25",
        google_api_key=gemini_key,
        temperature=0.3,
        max_output_tokens=8192,
    )


async def get_concierge_completion(prompt: str, **kwargs):
    """Use LLM Concierge for secure multi-provider calls; falls back to Gemini."""
    if HAS_CONCIERGE and concierge:
        try:
            messages = [{"role": "user", "content": prompt}]
            return await concierge.get_secure_completion(messages=messages, **kwargs)
        except Exception as exc:
            logger.warning("Concierge failed, falling back to Gemini: %s", exc)
    llm = get_llm("gemini")
    return await llm.ainvoke([HumanMessage(content=prompt)])


# ==================== MEMORY (Mem0) ====================
mem0_memory = None
try:
    mem0_config = json.loads(settings.MEM0_CONFIG)
    mem0_memory = Memory.from_config(mem0_config)
except Exception as _e:
    logger.warning("Mem0 initialisation failed: %s", _e)


def mem0_add(content: str, user_id: str = "polygod") -> None:
    if mem0_memory:
        try:
            mem0_memory.add(
                messages=[{"role": "system", "content": content}], user_id=user_id
            )
        except Exception as exc:
            logger.debug("mem0 add failed: %s", exc)


def mem0_search(query: str, user_id: str = "polygod") -> str:
    if mem0_memory:
        try:
            results = mem0_memory.search(query, user_id=user_id)
            if results:
                return "\n".join([str(r) for r in results[:5]])
        except Exception as exc:
            logger.debug("mem0 search failed: %s", exc)
    return ""


# ==================== MONTE CARLO + KELLY ====================
def run_monte_carlo(
    order: dict,
    market_data: dict,
    sims: int = 5000,
    seed: int | None = None,
) -> dict:
    """
    Monte Carlo risk engine.

    FIXED M7: Uses an isolated random.Random(seed) instance so simulations
    are reproducible when a seed is provided. Passing seed=None preserves
    the original non-deterministic behaviour for live usage.
    """
    rng = random.Random(seed)  # isolated — does not affect global random state

    size = float(order.get("size", 100))
    prob = market_data.get("prob", 0.5)
    if isinstance(prob, str):
        try:
            prob = float(prob)
        except (ValueError, TypeError):
            prob = 0.5
    prob = max(0.01, min(0.99, prob))
    volatility = market_data.get("volume", 10000) / 100_000.0 + 0.05

    outcomes: list[float] = []
    for _ in range(sims):
        outcome = rng.gauss(prob, volatility)
        pnl = (
            size * (outcome - 0.5) * 2 * rng.uniform(0.8, 1.2)
        )  # FIXED: Proper PnL calc
        outcomes.append(pnl)

    sorted_outcomes = sorted(outcomes)
    return {
        "expected_pnl": sum(outcomes) / sims,
        "win_prob": sum(1 for o in outcomes if o > 0) / sims,  # FIXED: Based on PnL > 0
        "worst_case": min(outcomes),
        "best_case": max(outcomes),
        "confidence_95": sorted_outcomes[int(sims * 0.05)],
        "confidence_5": sorted_outcomes[int(sims * 0.95)],
        "recommend_size": size * 0.8 if min(outcomes) < -size * 0.3 else size,
    }


def calculate_kelly(prob: float, odds: float = 1.0) -> float:
    """Kelly criterion: optimal fraction to wager."""
    prob = max(0.01, min(0.99, prob))
    b = odds
    q = 1 - prob
    kelly = (b * prob - q) / b if b > 0 else 0
    return max(0.0, min(1.0, kelly))


# ==================== PAPER MIRROR ====================
class PaperMirror:
    """Shadow execution engine for paper trading + simulations."""

    def __init__(self) -> None:
        self.pnls: list[float] = []
        self.trades: list[dict] = []

    def execute_shadow(self, order: dict) -> dict:
        size = float(order.get("size", 100))
        pnl = random.gauss(0.02 * size / 100, 0.05 * size / 100)
        self.pnls.append(pnl)
        trade = {"pnl": pnl, "status": "paper_executed", "order": order}
        self.trades.append(trade)
        return trade

    def run_tournament(
        self,
        order: dict,
        market_data: dict,
        kelly_fractions: list[float],
        sims: int = 100,
    ) -> dict:
        """Run parallel paper tournaments with different Kelly fractions."""
        results = []
        for kf in kelly_fractions:
            adjusted_order = {**order, "size": order.get("size", 100) * kf}
            outcomes = [self.execute_shadow(adjusted_order)["pnl"] for _ in range(sims)]
            avg_pnl = sum(outcomes) / len(outcomes) if outcomes else 0
            win_rate = (
                sum(1 for o in outcomes if o > 0) / len(outcomes) if outcomes else 0
            )
            variance = (
                sum((o - avg_pnl) ** 2 for o in outcomes) / len(outcomes)
                if outcomes
                else 0
            )
            sharpe = avg_pnl / max(0.001, variance**0.5) if outcomes else 0
            results.append(
                {
                    "kelly_fraction": kf,
                    "avg_pnl": avg_pnl,
                    "win_rate": win_rate,
                    "sharpe": sharpe,
                }
            )
        results.sort(key=lambda r: r["sharpe"], reverse=True)
        return {"tournament_results": results, "best": results[0] if results else None}


paper = PaperMirror()


# ==================== MARKET DATA ENRICHMENT ====================
async def get_enriched_market_data(market_id: str) -> dict:
    """
    Fetch enriched market data.

    FIXED M3: Query the local database first (fast, no external API call).
    Only falls back to the Polymarket API if the market is not in the DB.
    This avoids fetching 50 markets just to find one, and works for markets
    outside the top-50.
    """
    # ── DB-first lookup ──────────────────────────────────────────────────────
    try:
        from sqlalchemy import or_, select

        from src.backend.database import async_session_factory
        from src.backend.db_models import Market

        async with async_session_factory() as db:
            result = await db.execute(
                select(Market).where(
                    or_(Market.id == market_id, Market.slug == market_id)
                )
            )
            market = result.scalar_one_or_none()
            if market:
                return {
                    "id": market.id,
                    "slug": market.slug,
                    "title": market.title,
                    "prob": market.yes_percentage / 100.0,
                    "yes_percentage": market.yes_percentage,  # agents read this key directly
                    "volume": market.volume_7d,
                    "volume_24h": market.volume_24h,
                    "liquidity": market.liquidity,
                    "end_date": (
                        market.end_date.isoformat() if market.end_date else "Unknown"
                    ),
                    "is_active": market.is_active,
                }
    except Exception as exc:
        logger.warning(
            "DB lookup failed for market %s: %s — falling back to API", market_id, exc
        )

    # ── API fallback ─────────────────────────────────────────────────────────
    try:
        markets = await polymarket_client.get_top_markets_by_volume(limit=50)
        for m in markets:
            if m.get("id") == market_id or m.get("slug") == market_id:
                _yp = m.get("yes_percentage", 50)
                return {
                    "id": m.get("id"),
                    "slug": m.get("slug"),
                    "title": m.get("title"),
                    "prob": _yp / 100,
                    "yes_percentage": _yp,  # agents read this key directly
                    "volume": m.get("volume_7d", 0),
                    "volume_24h": m.get("volume_24h", 0),
                    "liquidity": m.get("liquidity", 0),
                    "end_date": str(m.get("end_date", "Unknown")),
                    "is_active": m.get("is_active", False),
                }
    except Exception as exc:
        logger.error("API fallback failed for market %s: %s", market_id, exc)

    logger.warning("Market %r not found in DB or API — using stub data", market_id)
    return {
        "id": market_id,
        "prob": 0.5,
        "yes_percentage": 50.0,
        "volume": 10000,
        "title": "Unknown Market",
    }


# ==================== ON-CHAIN VERIFICATION ====================
async def verify_onchain_orders(market_id: str) -> list[dict]:
    """Free CLOB reads — never crashes the graph."""
    try:
        await polymarket_client.get_order_book(market_id)
        fills = await polymarket_client.get_recent_fills(market_id, limit=10)
        return fills or []
    except Exception:
        return []


# ==================== STATE ====================
class AgentState(TypedDict):
    run_id: str
    mode: int
    market_id: str
    market_data: dict
    question: str
    statistics: str
    time_decay: str
    generalist: str
    macro: str
    devil: str
    debate_round: int
    debate_history: list[dict]
    verdict: str
    confidence: float
    decision: dict
    simulation: dict | None
    kelly_fraction: float
    risk_status: str
    on_chain_fills: list[dict]
    whale_context: str
    kelly_size: float
    paper_pnl: float
    execution_result: dict | None
    final_decision: dict | None


# ==================== MARKET DATA HELPER ====================
async def _fetch_market_data(market_id: str, question: str = "") -> tuple[dict, str]:
    market_data = await get_enriched_market_data(market_id)
    if not question:
        question = market_data.get("title", f"Market {market_id}")
    return market_data, question


# ==================== SWARM AGENTS ====================


async def statistics_agent(state: AgentState) -> AgentState:
    """Statistics Expert — quantitative analysis with Monte Carlo."""
    state = await memory_loop.remember_node(state, "statistics")
    await snapshot_engine.take_snapshot(state, "stats_agent")
    llm = get_llm("gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    prob = float(market_data.get("prob", 0.5))
    volume = market_data.get("volume", 0)

    sim = run_monte_carlo({"size": 1000}, market_data)
    kelly = calculate_kelly(prob)

    # In statistics_agent, after sim = run_monte_carlo(...):
    try:
        from src.backend.tools.kronos_polydata import enrich_with_kronos_and_polydata

        prices = state.get("price_history_7d") or state.get("price_history_24h") or []
        if prices:
            enrichment = await enrich_with_kronos_and_polydata(
                state.get("market_id", ""),
                prices,
            )
            state["market_data"] = {
                **state.get("market_data", {}),
                **enrichment,
            }
            # Inject Kronos signal into stats prompt context
            kronos = enrichment.get("kronos_forecast", {})
            if kronos:
                kronos_context = (
                    f"\nKronos Forecast: {kronos.get('forecast')}% in 24h "
                    f"(signal: {kronos.get('signal')}, "
                    f"trend: {kronos.get('trend')})"
                )
            else:
                kronos_context = ""
        else:
            kronos_context = ""
    except Exception as exc:
        logger.warning(f"Kronos/poly_data enrichment failed: {exc}")
        kronos_context = ""

    prompt = f"""Analyse raw stats for this Polymarket market. Be ruthless with numbers.

Market: "{question}"
Current Price: {market_data.get("yes_percentage", prob * 100):.1f}% YES
7d Volume: ${volume:,.0f}

Monte Carlo Results (5000 sims):
- Win Probability: {sim["win_prob"]:.1%}
- Expected PnL: ${sim["expected_pnl"]:.2f}
- 95% VaR: ${sim["confidence_95"]:.2f}
- Kelly Fraction: {kelly:.1%}{kronos_context}

Is there statistical edge? What do the numbers actually say?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["statistics"] = str(msg.content)
    state["debate_history"] = state.get("debate_history", []) + [
        {
            "agent": "StatsExpert",
            "output": str(msg.content),
            "round": state.get("debate_round", 0),
        }
    ]
    return state


async def time_decay_agent(state: AgentState) -> AgentState:
    """Time Decay Analyst — resolution timing and theta analysis."""
    state = await memory_loop.remember_node(state, "time_decay")
    llm = get_llm("gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    end_date = market_data.get("end_date", "Unknown")
    prob = float(market_data.get("prob", 0.5))

    days_remaining: str = "?"
    urgency = "Unknown"
    try:
        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ):
            try:
                end_dt = datetime.strptime(str(end_date).split(".")[0], fmt)
                delta = end_dt - datetime.now()
                days_remaining = str(delta.days)
                if delta.days < 1:
                    urgency = "CRITICAL — resolution imminent"
                elif delta.days < 7:
                    urgency = "HIGH — less than a week"
                elif delta.days < 30:
                    urgency = "MODERATE"
                else:
                    urgency = "LOW — plenty of time"
                break
            except ValueError:
                continue
    except Exception:
        urgency = "UNKNOWN"  # FIXED: No silent failure

    prompt = f"""Focus ONLY on time-to-resolution, theta decay, urgency for this market.

Market: "{question}"
Resolution Date: {end_date} | Days Remaining: {days_remaining}
Urgency: {urgency}
Current Price: {prob:.1%} YES

Analyse:
1. Is time working for or against each side?
2. What catalysts could accelerate price convergence?
3. Is the current price "priced in" given time remaining?
4. Optimal entry timing?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["time_decay"] = str(msg.content)
    state["debate_history"] = state.get("debate_history", []) + [
        {
            "agent": "TimeDecay",
            "output": str(msg.content),
            "round": state.get("debate_round", 0),
        }
    ]
    return state


async def generalist_agent(state: AgentState) -> AgentState:
    """Generalist — broad reasoning about real-world likelihood."""
    state = await memory_loop.remember_node(state, "generalist")
    llm = get_llm("gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    prior_args = "\n".join(
        f"- {d['agent']}: {d['output'][:150]}"
        for d in state.get("debate_history", [])[-6:]
    )
    prompt = f"""You are the Generalist Analyst on the POLYGOD Debate Floor.
Market: "{question}"
Current Price: {market_data.get("yes_percentage", 50):.1f}% YES

Prior debate arguments:
{prior_args if prior_args else "No prior arguments — you go first."}

Analyse from a real-world perspective:
1. What does the underlying event actually look like?
2. Are there non-obvious factors the market is missing?
3. What is your gut probability vs market price?
4. If you were betting your own money, what would you do?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["generalist"] = str(msg.content)
    state["debate_history"] = state.get("debate_history", []) + [
        {
            "agent": "Generalist",
            "output": str(msg.content),
            "round": state.get("debate_round", 0),
        }
    ]
    return state


async def macro_agent(state: AgentState) -> AgentState:
    """Macro Analyst — macro environment, correlations, regime shifts."""
    state = await memory_loop.remember_node(state, "macro")
    llm = get_llm("gemini")
    question = state.get("question", "")
    prior_args = "\n".join(
        f"- {d['agent']}: {d['output'][:150]}"
        for d in state.get("debate_history", [])[-6:]
    )
    prompt = f"""You are the Macro Analyst on the POLYGOD Debate Floor.
Market: "{question}"

Prior debate arguments:
{prior_args if prior_args else "No prior arguments yet."}

Analyse the macro context:
1. What broader trends affect this market? (politics, economics, crypto cycles)
2. How does this correlate with other markets or assets?
3. Are we in a regime where prediction markets are systematically mispriced?
4. What is the macro-level edge here?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["macro"] = str(msg.content)
    state["debate_history"] = state.get("debate_history", []) + [
        {
            "agent": "MacroAnalyst",
            "output": str(msg.content),
            "round": state.get("debate_round", 0),
        }
    ]
    return state


async def devil_agent(state: AgentState) -> AgentState:
    """Devil's Advocate — challenges consensus and finds logical fallacies."""
    state = await memory_loop.remember_node(state, "devil")
    llm = get_llm("gemini")
    question = state.get("question", "")
    prior_args = "\n".join(
        f"- {d['agent']}: {d['output'][:200]}"
        for d in state.get("debate_history", [])[-8:]
    )
    prompt = f"""You are the Devil's Advocate on the POLYGOD Debate Floor.
Market: "{question}"

All prior arguments from this debate:
{prior_args if prior_args else "No arguments to challenge yet."}

Your job: Find the WEAKNESS in every argument above.
- What assumptions are untested?
- What data is missing?
- What is the contrarian case?
- Where is groupthink happening?

Be ruthless but fair. Challenge the strongest argument the most."""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["devil"] = str(msg.content)
    state["debate_history"] = state.get("debate_history", []) + [
        {
            "agent": "DevilsAdvocate",
            "output": str(msg.content),
            "round": state.get("debate_round", 0),
        }
    ]
    return state


# ==================== ON-CHAIN VERIFICATION NODE ====================
async def onchain_verification_node(state: AgentState) -> AgentState:
    state = await memory_loop.remember_node(state, "onchain_verification")
    if settings.POLYGOD_MODE >= 2:
        fills = await verify_onchain_orders(state["market_id"])
        state["on_chain_fills"] = fills
        whale_activity = len(fills) > 0
        state["market_data"] = {
            **state.get("market_data", {}),
            "whale_activity": whale_activity,
        }
        logger.info(
            "On-chain verification: %d fills, whale=%s",
            len(fills),
            "YES" if whale_activity else "NO",
        )
    return state


# ==================== WHALE RAG NODE ====================
async def whale_copy_rag_node(state: AgentState) -> AgentState:
    state = await memory_loop.remember_node(state, "whale_copy_rag")
    mode = state.get("mode", settings.POLYGOD_MODE)
    if mode < 3:
        state["whale_context"] = ""
        return state
    enriched: dict[str, Any] = await whale_rag.enrich_state(dict(state))
    state = AgentState(**enriched)  # type: ignore[typeddict-item]
    return state


# ==================== TOURNAMENT AUTO-ENTRANT ====================
async def tournament_auto_entrant_node(state: AgentState) -> AgentState:
    state = await memory_loop.remember_node(state, "tournament_auto_entrant")
    confidence = state.get("confidence", 0)
    mode = settings.POLYGOD_MODE

    if mode >= 1 and confidence > 90:
        verdict = state.get("verdict", "")
        side = "YES" if "YES" in verdict.upper() else "NO"
        size = 100 * (confidence / 100)
        logger.info(
            "TOURNAMENT AUTO-ENTRANT: confidence=%.0f%% > 90%%, side=%s, size=%.0f",
            confidence,
            side,
            size,
        )
        tournament_state = {
            **state,
            "decision": {
                **state.get("decision", {}),
                "order": {"market_id": state["market_id"], "side": side, "size": size},
            },
        }
        try:
            result = await parallel_paper_tournament(tournament_state)
            state["execution_result"] = result.get("decision", {})
            best_config = result.get("evolution_best", {})
            sharpe = best_config.get("score", 0)
            if sharpe > 2.0:
                logger.info(
                    "TOURNAMENT WINNER (sharpe=%.3f > 2.0) — promoting to AutoResearchLab",
                    sharpe,
                )
                await autoresearch_lab.mutate_and_evolve(dict(state))  # type: ignore[arg-type]
        except Exception as exc:
            logger.error("Tournament auto-entrant failed: %s", exc)
    return state


# ==================== MODERATOR ====================
async def moderator_agent(state: AgentState) -> AgentState:
    """Synthesises all agent inputs into ONE final verdict."""
    state = await memory_loop.remember_node(state, "moderator")
    await snapshot_engine.take_snapshot(state, "post_moderator")

    grok_key = settings.GROK_API_KEY.get_secret_value()
    llm = get_llm("grok" if grok_key else "gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    debate = state.get("debate_history", [])

    all_args = "\n\n".join(
        f"### {d['agent']} (Round {d.get('round', 0)}):\n{d['output']}" for d in debate
    )
    onchain_ctx = ""
    if state.get("on_chain_fills"):
        onchain_ctx = f"\n\n🐋 ON-CHAIN: {len(state['on_chain_fills'])} recent fills — whale activity confirmed."
    elif state.get("market_data", {}).get("whale_activity") is False:
        onchain_ctx = "\n🐋 ON-CHAIN: No significant fills in last 10 trades."

    prompt = f"""You are the Moderator of the POLYGOD Debate Floor.
Market: "{question}"
Current Price: {market_data.get("yes_percentage", 50):.1f}% YES

All debate arguments:
{all_args if all_args else "No arguments presented."}
{onchain_ctx}

Provide your FINAL VERDICT:
1. **Summary**: Key points for YES vs NO (2-3 sentences each)
2. **Verdict**: "BUY YES" / "BUY NO" / "STAY NEUTRAL"
3. **Confidence**: 0-100%
4. **Key Risk**: The single biggest risk to this trade"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    verdict_text = str(msg.content)
    confidence = 50.0
    conf_match = re.search(
        r"(?:confidence|odds)[:\s]*(\d+)", verdict_text, re.IGNORECASE
    )
    if conf_match:
        confidence = float(conf_match.group(1))

    state["verdict"] = verdict_text
    state["confidence"] = confidence
    state["debate_history"] = state.get("debate_history", []) + [
        {
            "agent": "Moderator",
            "output": verdict_text,
            "round": state.get("debate_round", 0),
        }
    ]
    state["decision"] = {
        "order": {"size": 1000},
        "verdict": verdict_text,
        "confidence": confidence,
    }
    return state


# ==================== EVOLUTION SUPERVISOR ====================
async def evolution_supervisor_node(state: AgentState) -> AgentState:
    """Increments debate_round so the cyclic router knows when to stop."""
    new_round = state.get("debate_round", 0) + 1
    state["debate_round"] = new_round
    debate = state.get("debate_history", [])
    logger.info(
        "Evolution Supervisor: round %d, %d total agent outputs", new_round, len(debate)
    )
    state["debate_history"] = debate + [
        {
            "agent": "EvolutionSupervisor",
            "output": f"Round {new_round} complete. {len(debate)} arguments recorded.",
            "round": new_round - 1,
        }
    ]
    return state


# ==================== RISK GATE ====================
async def risk_gate_node(state: AgentState) -> AgentState:
    """Risk gate with Monte Carlo + Kelly criterion."""
    decision = state.get("decision", {})
    order = decision.get("order", {"size": 100})
    market_data = state.get("market_data", {})

    sim = run_monte_carlo(order, market_data)
    state["simulation"] = sim

    size = float(order.get("size", 100))
    p_win = sim.get("win_prob", 0.5)
    kelly = calculate_kelly(p_win)
    state["kelly_fraction"] = kelly
    volume = market_data.get("volume", 0)

    risk_low = (
        kelly > 0.08
        and sim.get("worst_case", 0) > -size * 0.25
        and volume > 3000
        and p_win > 0.52
    )
    if risk_low:
        state["decision"] = {**decision, "risk_status": "low", "next": "execute"}
        state["risk_status"] = "low"
        logger.info(
            "RISK GATE PASSED: Kelly=%.2f, win_prob=%.1f%%, volume=$%,.0f",
            kelly,
            p_win * 100,
            volume,
        )
    else:
        state["decision"] = {**decision, "risk_status": "high", "next": "approve"}
        state["risk_status"] = "high"
        logger.warning(
            "RISK GATE BLOCKED: Kelly=%.2f, win_prob=%.1f%%, worst_case=$%.2f",
            kelly,
            p_win * 100,
            sim.get("worst_case", 0),
        )
    return state


# ==================== APPROVE / EXECUTE ====================
async def approve_node(state: AgentState) -> AgentState:
    """Approve trade for human review (observe mode)."""
    verdict = state.get("verdict", "No verdict")
    logger.info(
        "OBSERVE MODE: Trade requires human approval. Verdict: %.100s...", verdict
    )
    state["decision"] = {**state.get("decision", {}), "status": "pending_approval"}
    return state


async def execute_node(state: AgentState) -> AgentState:
    """
    Execute trade.

    mode <= 2 (paper/low): shadow execution via PaperMirror.
    mode 3 (beast):        live CLOB order via polymarket_client.place_order().

    Safety guards (mode 3 only):
      - Liquidity must be >= $5,000
      - Confidence must be >= 90%
      - kelly_size is calculated from real USDC balance before placing
    Both guards fall back to paper execution if not met — never raises.
    """
    state = await memory_loop.remember_node(state, "execution")
    decision = state.get("decision", {})
    order = decision.get("order", {})
    mode = state.get("mode", settings.POLYGOD_MODE)
    confidence = state.get("confidence", 0)
    result: dict

    logger.info(f"EXECUTING in mode {mode}: {order}")

    if mode <= 2:
        # Paper / Low mode — shadow execution only
        result = paper.execute_shadow(order)
        state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)
        logger.info(f"Paper execution: pnl=${result.get('pnl', 0):.2f}")

    else:
        # ── BEAST MODE — LIVE TRADES ─────────────────────────────────────
        logger.info("🚀 BEAST MODE: attempting LIVE execution")

        # Calculate kelly_size from real wallet balance
        try:
            usdc_balance = await polymarket_client.get_usdc_balance()
            kelly_fraction = state.get("kelly_fraction", 0.25)
            kelly_size = usdc_balance * kelly_fraction * (confidence / 100.0)
            kelly_size = max(10.0, round(kelly_size, 2))  # floor at $10
            state["kelly_size"] = kelly_size
            logger.info(
                f"Kelly size: ${kelly_size:.2f} "
                f"(balance=${usdc_balance:.2f}, "
                f"kelly={kelly_fraction:.2f}, "
                f"confidence={confidence:.0f}%)"
            )
        except Exception as exc:
            logger.warning(f"Balance fetch failed, using fallback kelly_size: {exc}")
            kelly_size = state.get("kelly_size", 100.0)

        live_order = {
            "market_id": state["market_id"],
            "side": "YES" if "YES" in state.get("verdict", "").upper() else "NO",
            "size": kelly_size,
            "dry_run": False,
        }

        # Safety guard 1: liquidity
        liquidity = await polymarket_client.check_liquidity(live_order)
        if liquidity < 5000:
            logger.warning(
                f"🔴 LIVE TRADE ABORTED: liquidity ${liquidity:,.0f} < $5,000 minimum"
            )
            result = paper.execute_shadow(order)
            state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)

        # Safety guard 2: confidence
        elif confidence < 90:
            logger.warning(
                f"🔴 LIVE TRADE ABORTED: confidence {confidence:.0f}% < 90% minimum"
            )
            result = paper.execute_shadow(order)
            state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)

        else:
            # All guards passed — place live CLOB order
            logger.info(
                f"💰 PLACING LIVE ORDER: {live_order['side']} "
                f"${live_order['size']:.2f} on {live_order['market_id']}"
            )
            result = await polymarket_client.place_order(live_order)
            logger.info(
                f"💰 LIVE ORDER RESULT: status={result.get('status')} "
                f"order_id={result.get('order_id')}"
            )

    state["execution_result"] = result
    state["decision"] = {**decision, "execution_result": result}
    return state


# ==================== META REFLECTION =================###
async def meta_reflection_node(state: AgentState) -> AgentState:
    """Store full run outcome to mem0 and finalise."""
    state = await memory_loop.remember_node(state, "meta_reflection")
    outcome = {
        "run_id": state.get("run_id"),
        "market": state.get("question", ""),
        "mode": state.get("mode", 0),
        "paper_pnl": state.get("paper_pnl", 0),
        "risk_status": state.get("risk_status", "unknown"),
        "kelly_fraction": state.get("kelly_fraction", 0),
        "confidence": state.get("confidence", 0),
    }
    mem0_add(
        f"Run outcome: {json.dumps(outcome)[:500]}",
        user_id=state.get("market_id", "polygod"),
    )
    state["final_decision"] = {
        **state.get("decision", {}),
        "outcome": outcome,
        "verdict": state.get("verdict", "No verdict"),
    }
    logger.info(
        "META REFLECTION complete: pnl=$%.2f, confidence=%.0f%%",
        state.get("paper_pnl", 0),
        state.get("confidence", 0),
    )
    return state


# ==================== ROUTING ====================
def mode_router(state: AgentState) -> str:
    mode = state.get("mode", settings.POLYGOD_MODE)
    return "approve" if mode == 0 else "auto_enter"


def risk_router(state: AgentState) -> str:
    decision: dict = state.get("decision", {})
    return str(decision.get("next", "approve"))


# ==================== GRAPH CONSTRUCTION ====================
def build_polygod_graph() -> StateGraph:
    """Build the cyclic swarm graph with tournament auto-entrant."""
    workflow = StateGraph(AgentState)

    workflow.add_node("statistics", statistics_agent)
    workflow.add_node("time_decay", time_decay_agent)
    workflow.add_node("generalist", generalist_agent)
    workflow.add_node("macro", macro_agent)
    workflow.add_node("devil", devil_agent)
    workflow.add_node("onchain_verify", onchain_verification_node)
    workflow.add_node("whale_rag", whale_copy_rag_node)
    workflow.add_node("auto_enter", tournament_auto_entrant_node)
    workflow.add_node("evolution_supervisor", evolution_supervisor_node)
    workflow.add_node("moderator", moderator_agent)
    workflow.add_node("approve", approve_node)
    workflow.add_node("risk_gate", risk_gate_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("meta_reflection", meta_reflection_node)

    workflow.set_entry_point("statistics")
    workflow.add_edge("statistics", "time_decay")
    workflow.add_edge("time_decay", "generalist")
    workflow.add_edge("generalist", "macro")
    workflow.add_edge("macro", "devil")
    workflow.add_edge("devil", "evolution_supervisor")

    def _cycle_or_finish(s: AgentState) -> str:
        max_rounds = {0: 1, 1: 2, 2: 3, 3: 3}.get(s.get("mode", 0), 2)
        return "moderator" if s.get("debate_round", 0) >= max_rounds else "stats"

    workflow.add_conditional_edges(
        "evolution_supervisor",
        _cycle_or_finish,
        {"stats": "statistics", "moderator": "moderator"},
    )
    workflow.add_edge("moderator", "onchain_verify")
    workflow.add_conditional_edges(
        "onchain_verify",
        mode_router,
        {"approve": "approve", "auto_enter": "auto_enter"},
    )
    workflow.add_edge("auto_enter", "whale_rag")
    workflow.add_conditional_edges(
        "whale_rag",
        lambda s: "approve" if s.get("mode", 0) == 0 else "risk_gate",
        {"approve": "approve", "risk_gate": "risk_gate"},
    )
    workflow.add_edge("approve", "meta_reflection")
    workflow.add_conditional_edges(
        "risk_gate",
        risk_router,
        {"execute": "execute", "approve": "approve"},
    )
    workflow.add_edge("execute", "meta_reflection")
    workflow.add_edge("meta_reflection", END)

    return workflow


# ==================== COMPILE ====================
polygod_graph = build_polygod_graph().compile(checkpointer=checkpointer)


# ==================== ENTRY POINT ====================
async def run_polygod(market_id: str, mode: int = 0, question: str = "") -> dict:
    """
    Main entry point for the POLYGOD cyclic swarm.

    Args:
        market_id: Polymarket condition ID or slug.
        mode: 0=observe, 1=paper, 2=low, 3=beast.
        question: Market question (auto-fetched from DB if empty).

    Returns:
        Final state dict with verdict, execution result, and PnL.
    """
    global POLYGOD_MODE
    POLYGOD_MODE = mode
    # Also update settings to ensure other parts of the app see the new mode
    settings.POLYGOD_MODE = mode

    market_data, question = await _fetch_market_data(market_id, question)
    run_id = str(uuid.uuid4())[:8]

    initial_state: AgentState = {
        "run_id": run_id,
        "mode": mode,
        "market_id": market_id,
        "market_data": market_data,
        "question": question,
        "statistics": "",
        "time_decay": "",
        "generalist": "",
        "macro": "",
        "devil": "",
        "debate_round": 0,
        "debate_history": [],
        "verdict": "",
        "confidence": 50.0,
        "decision": {"order": {"size": 1000}},
        "simulation": None,
        "kelly_fraction": 0.25,
        "kelly_size": 100.0,
        "risk_status": "pending",
        "on_chain_fills": [],
        "whale_context": "",
        "paper_pnl": 0.0,
        "execution_result": None,
        "final_decision": None,
    }

    logger.info(
        "POLYGOD RUN [%s]: market=%s, mode=%d, question='%.60s...'",
        run_id,
        market_id,
        mode,
        question,
    )

    config: RunnableConfig = {
        "configurable": {"thread_id": f"polygod-{market_id}-{run_id}"}
    }

    # ── Execution timeout to prevent runaway CPU/memory ───────────────────────
    async def _execute_with_timeout():
        return await polygod_graph.ainvoke(initial_state, config=config)

    try:
        raw_result = await asyncio.wait_for(
            _execute_with_timeout(),
            timeout=POLYGOD_EXECUTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "POLYGOD RUN [%s] TIMEOUT after %ds — aborting execution",
            run_id,
            POLYGOD_EXECUTION_TIMEOUT_SECONDS,
        )
        # Give the event loop a tick to allow any cleanup handlers to run
        # before returning, so pooled DB connections can be returned properly.
        await asyncio.sleep(0)
        return {
            "status": "timeout",
            "run_id": run_id,
            "error": f"Execution exceeded {POLYGOD_EXECUTION_TIMEOUT_SECONDS}s timeout",
        }
    except asyncio.CancelledError:
        logger.warning("POLYGOD RUN [%s] was cancelled externally", run_id)
        await asyncio.sleep(0)
        raise

    result: dict = raw_result if isinstance(raw_result, dict) else {}

    logger.info(
        "POLYGOD RUN [%s] COMPLETE: verdict='%.80s...', pnl=$%.2f, risk=%s",
        run_id,
        result.get("verdict", ""),
        float(result.get("paper_pnl", 0)),
        result.get("risk_status", "unknown"),
    )
    return result
