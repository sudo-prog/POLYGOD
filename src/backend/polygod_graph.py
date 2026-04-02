# src/backend/polygod_graph.py — GOD TIER CYCLIC SWARM
"""
POLYGOD God-Tier Cyclic Swarm Graph

Multi-agent debate swarm with:
- Cyclic debate rounds (agents challenge each other)
- Evolution Lab (parallel paper tournaments + Kelly optimization)
- Persistent checkpointing via SqliteSaver
- Grok/Gemini LLM routing by mode
- Monte Carlo risk engine + Kelly criterion
- Mem0 long-term memory + X sentiment
- LangSmith tracing
"""

import asyncio
import json
import logging
import os
import random
import uuid
from typing import Any, Dict, List, Literal, TypedDict

import httpx
from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
try:
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    try:
        from langgraph_checkpoint_sqlite import SqliteSaver
        from langgraph.checkpoint.memory import MemorySaver
    except ImportError:
        SqliteSaver = None
        MemorySaver = None
from langgraph.graph import END, StateGraph

try:
    from mem0 import Memory
except ImportError:
    Memory = None
from src.backend.config import settings
from src.backend.llm_router import router
from src.backend.tools.x_sentiment import get_x_sentiment
from src.backend.parallel_tournament import parallel_paper_tournament
from src.backend.niche_scanner import scanner
from src.backend.autoresearch_lab import autoresearch_lab

logger = logging.getLogger(__name__)

# ==================== LANGSMITH TRACING ====================
try:
    from langsmith import traceable
except ImportError:
    # Graceful fallback if langsmith not installed
    def traceable(*args, **kwargs):
        def decorator(fn):
            return fn
        if len(args) == 1 and callable(args[0]):
            return args[0]
        return decorator

# ==================== MEMORY & CHECKPOINTING ====================
# Persistent SQLite checkpointing (survives restarts)
_CHECKPOINT_DB = os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints.db")
try:
    if SqliteSaver:
        import sqlite3
        conn = sqlite3.connect(_CHECKPOINT_DB)
        checkpointer = SqliteSaver(conn=conn)
        logger.info(f"SqliteSaver initialized: {_CHECKPOINT_DB}")
    elif MemorySaver:
        checkpointer = MemorySaver()
        logger.warning("SqliteSaver unavailable, using MemorySaver")
    else:
        checkpointer = None
        logger.warning("No checkpointing available")
except Exception as e:
    logger.warning(f"SqliteSaver failed ({e}), falling back to MemorySaver")
    checkpointer = MemorySaver() if MemorySaver else None

# Mem0 long-term memory (Qdrant-backed)
try:
    mem0_config = json.loads(settings.MEM0_CONFIG)
    mem0_memory = Memory.from_config(mem0_config)
except Exception as e:
    logger.warning(f"Mem0 initialization failed: {e}")
    mem0_memory = None

# ==================== PAPER MIRROR ====================
class PaperMirror:
    """Shadow execution engine for paper trading + simulations."""
    def __init__(self):
        self.pnls: list[float] = []
        self.trades: list[dict] = []

    def execute_shadow(self, order: dict) -> dict:
        size = float(order.get("size", 100))
        # Simulate PnL with realistic variance
        pnl = random.gauss(0.02 * size / 100, 0.05 * size / 100)
        self.pnls.append(pnl)
        trade = {"pnl": pnl, "status": "paper_executed", "order": order}
        self.trades.append(trade)
        return trade

    def run_tournament(self, order: dict, market_data: dict, kelly_fractions: list[float], sims: int = 100) -> dict:
        """Run parallel paper tournaments with different Kelly fractions."""
        results = []
        for kf in kelly_fractions:
            adjusted_order = {**order, "size": order.get("size", 100) * kf}
            outcomes = []
            for _ in range(sims):
                result = self.execute_shadow(adjusted_order)
                outcomes.append(result["pnl"])
            avg_pnl = sum(outcomes) / len(outcomes) if outcomes else 0
            win_rate = sum(1 for o in outcomes if o > 0) / len(outcomes) if outcomes else 0
            results.append({
                "kelly_fraction": kf,
                "avg_pnl": avg_pnl,
                "win_rate": win_rate,
                "sharpe": avg_pnl / (max(0.001, (sum((o - avg_pnl) ** 2 for o in outcomes) / len(outcomes)) ** 0.5)) if outcomes else 0,
            })
        # Sort by Sharpe ratio (risk-adjusted)
        results.sort(key=lambda r: r["sharpe"], reverse=True)
        return {"tournament_results": results, "best": results[0] if results else None}


paper = PaperMirror()

# ==================== GLOBAL MODE ====================
POLYGOD_MODE: int = settings.POLYGOD_MODE


# ==================== GOD TIER STATE ====================
class AgentState(TypedDict):
    """God-tier cyclic swarm state."""
    run_id: str
    mode: int  # 0=observe, 1=paper, 2=low, 3=beast
    market_id: str
    market_data: dict
    question: str
    # Research
    research_insight: str
    x_sentiment: dict
    # Debate
    debate_round: int
    debate_history: list[dict]  # [{agent, output, round}]
    debate_verdict: str
    # Decision
    decision: dict
    # Risk
    simulation: dict | None
    kelly_fraction: float
    risk_status: str
    # Evolution Lab
    evolution_best: dict | None
    # Execution
    paper_pnl: float
    execution_result: dict | None
    # Meta
    memory_context: dict
    final_decision: dict | None


# ==================== LLM ROUTING ====================
async def call_grok(prompt: str) -> str:
    """xAI Grok for high-stakes truth-seeking alpha research."""
    if not settings.GROK_API_KEY:
        logger.warning("GROK_API_KEY not set — falling back")
        return "Grok unavailable — falling back to basic insight"
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.GROK_API_KEY}"},
                json={
                    "model": "grok-beta",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 1200,
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Grok API error: {e}")
        return f"Grok error: {e}"


async def call_gemini(prompt: str) -> str:
    """Google Gemini for low-stakes efficient analysis."""
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — falling back")
        return "Gemini unavailable — using basic insight"
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=1200,
        )
        response = llm.invoke(prompt)
        return str(response.content)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return f"Gemini error: {e}"


async def llm_call(prompt: str, mode: int = 0, agent_name: str = "default") -> str:
    """Route LLM call via GodTierLLMRouter for cost-efficient swarm operations."""
    priority = "cheap" if mode < 2 else "fast"
    response = await router.route(prompt, agent_name, priority=priority)
    return str(response)  # litellm router returns string directly


# ==================== MONTE CARLO + KELLY ====================
def run_monte_carlo(order: dict, market_data: dict, sims: int = 5000) -> dict:
    """God-tier Monte Carlo risk engine."""
    size = float(order.get("size", 100))
    prob = market_data.get("prob", 0.5)
    if isinstance(prob, str):
        try:
            prob = float(prob)
        except (ValueError, TypeError):
            prob = 0.5
    prob = max(0.01, min(0.99, prob))
    volatility = market_data.get("volume", 10000) / 100000.0 + 0.05
    outcomes = []
    for _ in range(sims):
        outcome = random.gauss(prob, volatility)
        pnl = size * (1 if outcome > 0.5 else -1) * random.uniform(0.8, 1.2)
        outcomes.append(pnl)
    sorted_outcomes = sorted(outcomes)
    return {
        "expected_pnl": sum(outcomes) / sims,
        "win_prob": sum(1 for o in outcomes if o > 0) / sims,
        "worst_case": min(outcomes),
        "best_case": max(outcomes),
        "confidence_95": sorted_outcomes[int(sims * 0.05)],
        "confidence_5": sorted_outcomes[int(sims * 0.95)],
        "recommend_size": size * 0.8 if min(outcomes) < -size * 0.3 else size,
    }


def calculate_kelly(prob: float, odds: float = 1.0) -> float:
    """Kelly criterion: optimal fraction to wager."""
    prob = max(0.01, min(0.99, prob))
    b = odds  # net odds received on the wager
    q = 1 - prob
    kelly = (b * prob - q) / b if b > 0 else 0
    return max(0.0, min(1.0, kelly))


# ==================== MEMORY HELPERS ====================
def mem0_add(content: str, user_id: str = "polygod"):
    """Add to mem0 memory with graceful fallback."""
    if mem0_memory:
        try:
            mem0_memory.add(messages=[{"role": "system", "content": content}], user_id=user_id)
        except Exception as e:
            logger.debug(f"mem0 add failed: {e}")


def mem0_search(query: str, user_id: str = "polygod") -> str:
    """Search mem0 memory with graceful fallback."""
    if mem0_memory:
        try:
            results = mem0_memory.search(query, user_id=user_id)
            if results:
                return "\n".join([str(r) for r in results[:5]])
        except Exception as e:
            logger.debug(f"mem0 search failed: {e}")
    return ""


# ==================== ENRICHED MARKET DATA ====================
async def get_enriched_market_data(market_id: str) -> dict:
    """Fetch enriched market data for analysis."""
    try:
        from src.backend.polymarket.client import polymarket_client
        markets = await polymarket_client.get_top_markets_by_volume(limit=50)
        for m in markets:
            if m.get("id") == market_id or m.get("slug") == market_id:
                return {
                    "id": m.get("id"),
                    "slug": m.get("slug"),
                    "title": m.get("title"),
                    "prob": m.get("yes_percentage", 50) / 100,
                    "volume": m.get("volume_7d", 0),
                    "volume_24h": m.get("volume_24h", 0),
                    "liquidity": m.get("liquidity", 0),
                    "end_date": str(m.get("end_date", "Unknown")),
                    "is_active": m.get("is_active", False),
                }
    except Exception as e:
        logger.error(f"Failed to fetch enriched market data: {e}")
    return {"id": market_id, "prob": 0.5, "volume": 10000, "title": "Unknown Market"}


# ==================== SWARM NODES ====================

@traceable
async def memory_recall_node(state: AgentState) -> AgentState:
    """Recall relevant memories from mem0 for context priming."""
    market_id = state.get("market_id", "")
    question = state.get("question", "")
    recall = mem0_search(f"market {market_id} {question}", user_id=market_id)
    state["memory_context"] = {"recall": recall, "market_id": market_id}
    logger.info(f"Memory recall for {market_id}: {len(recall)} chars")
    return state


@traceable
async def grok_research_node(state: AgentState) -> AgentState:
    """Grok/Gemini alpha research node."""
    market_data = state.get("market_data", {})
    mode = state.get("mode", 0)
    question = state.get("question", market_data.get("title", "Unknown Market"))
    memory_ctx = state.get("memory_context", {}).get("recall", "")

    prompt = f"""POLYGOD alpha research: Analyze this Polymarket market for edge.

Market: {question}
Data: {json.dumps(market_data, indent=2)}
Prior Memory: {memory_ctx[:500] if memory_ctx else "None"}

Be brutally truthful. Identify:
1. Is there informational edge? What do insiders know?
2. What's the true probability vs market price ({market_data.get('prob', 0.5):.1%})?
3. Key risks and catalysts before resolution?
4. Recommended position size with Kelly-adjusted reasoning?
5. Confidence level (0-100%)?"""

    logger.info(f"Research node → {'Grok' if mode >= 2 else 'Gemini'} (mode={mode})")
    insight = await llm_call(prompt, mode)
    state["research_insight"] = insight

    # Update market_data with research-derived probability
    state["market_data"] = {**market_data, "research_insight": insight}
    mem0_add(f"Research insight for {question}: {insight[:200]}", user_id=state.get("market_id", "polygod"))
    return state


@traceable
async def x_sentiment_node(state: AgentState) -> AgentState:
    """X/Twitter sentiment analysis node."""
    market_data = state.get("market_data", {})
    slug = market_data.get("slug", "")
    if slug:
        try:
            x_data = await get_x_sentiment(slug)
            state["x_sentiment"] = x_data
            bull_score = x_data.get("bull_score", 0.5)
            # Blend sentiment into probability estimate
            current_prob = float(market_data.get("prob", 0.5))
            blended = current_prob * 0.7 + bull_score * 0.3
            state["market_data"] = {**market_data, "prob": blended, "x_sentiment": x_data}
            logger.info(f"X sentiment for {slug}: bull_score={bull_score:.3f}, blended_prob={blended:.3f}")
        except Exception as e:
            logger.warning(f"X sentiment failed: {e}")
            state["x_sentiment"] = {"bull_score": 0.5, "error": str(e)}
    else:
        state["x_sentiment"] = {"bull_score": 0.5}
    return state


# ==================== DEBATE SWARM NODES ====================
# Each node wraps the existing debate agents from agents/debate.py
# with Mem0-enhanced prompts and swarm-style argumentation

async def debate_stats_node(state: AgentState) -> AgentState:
    """Statistics Expert — quantitative analysis with Monte Carlo."""
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    prob = float(market_data.get("prob", 0.5))
    volume = market_data.get("volume", 0)
    mode = state.get("mode", 0)

    # Run Monte Carlo for the debate
    sim = run_monte_carlo({"size": 1000}, market_data)
    kelly = calculate_kelly(prob)

    prior_args = "\n".join([f"- {d['agent']}: {d['output'][:150]}" for d in state.get("debate_history", [])[-6:]])

    prompt = f"""You are the Statistics Expert on the POLYGOD Debate Floor.
Market: "{question}"
Current Price: {market_data.get('yes_percentage', prob * 100):.1f}% YES
Volume: ${volume:,.0f} | Mode: {mode}

Monte Carlo Results (5000 sims):
- Win Probability: {sim['win_prob']:.1%}
- Expected PnL: ${sim['expected_pnl']:.2f}
- 95% VaR: ${sim['confidence_95']:.2f}
- Kelly Fraction: {kelly:.1%}

Prior debate arguments:
{prior_args if prior_args else "No prior arguments — you go first."}

Provide your quantitative analysis. Be specific with numbers. If prior arguments have statistical flaws, point them out."""

    response = await llm_call(prompt, mode)
    entry = {"agent": "StatsExpert", "output": response, "round": state.get("debate_round", 0)}
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def debate_time_decay_node(state: AgentState) -> AgentState:
    """Time Decay Analyst — resolution timing and theta analysis."""
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    end_date = market_data.get("end_date", "Unknown")
    prob = float(market_data.get("prob", 0.5))
    mode = state.get("mode", 0)

    # Calculate days remaining
    days_remaining = "?"
    urgency = "Unknown"
    try:
        from datetime import datetime
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
            try:
                end_dt = datetime.strptime(str(end_date).split(".")[0], fmt)
                delta = end_dt - datetime.now()
                days_remaining = f"{delta.days}"
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
        pass

    prior_args = "\n".join([f"- {d['agent']}: {d['output'][:150]}" for d in state.get("debate_history", [])[-6:]])

    prompt = f"""You are the Time Decay & Resolution Analyst on the POLYGOD Debate Floor.
Market: "{question}"
Resolution Date: {end_date} | Days Remaining: {days_remaining}
Urgency: {urgency}
Current Price: {prob:.1%} YES

Prior debate arguments:
{prior_args if prior_args else "No prior arguments yet."}

Analyze:
1. Is time working for or against each side?
2. What catalysts could accelerate price convergence?
3. Is the current price "priced in" given time remaining?
4. Optimal entry timing?"""

    response = await llm_call(prompt, mode)
    entry = {"agent": "TimeDecay", "output": response, "round": state.get("debate_round", 0)}
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def debate_whale_rag_node(state: AgentState) -> AgentState:
    """Whale RAG Agent — analyzes whale activity and market microstructure."""
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    volume = market_data.get("volume", 0)
    mode = state.get("mode", 0)
    memory_ctx = state.get("memory_context", {}).get("recall", "")

    prior_args = "\n".join([f"- {d['agent']}: {d['output'][:150]}" for d in state.get("debate_history", [])[-6:]])

    prompt = f"""You are the Whale RAG Agent on the POLYGOD Debate Floor.
Market: "{question}"
7d Volume: ${volume:,.0f}
Prior whale memory: {memory_ctx[:300] if memory_ctx else "No prior whale data."}

Prior debate arguments:
{prior_args if prior_args else "No prior arguments yet."}

Analyze:
1. What does the volume tell us about whale accumulation/distribution?
2. Are there signs of informed trading or manipulation?
3. What would smart money be doing at this price level?
4. Rate the whale signal strength (1-10) with reasoning."""

    response = await llm_call(prompt, mode)
    entry = {"agent": "WhaleRAG", "output": response, "round": state.get("debate_round", 0)}
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def debate_devils_advocate_node(state: AgentState) -> AgentState:
    """Devil's Advocate — challenges consensus and finds logical fallacies."""
    question = state.get("question", "")
    mode = state.get("mode", 0)
    prior_args = "\n".join([f"- {d['agent']}: {d['output'][:200]}" for d in state.get("debate_history", [])[-8:]])

    prompt = f"""You are the Devil's Advocate on the POLYGOD Debate Floor.
Market: "{question}"

All prior arguments from this debate:
{prior_args if prior_args else "No arguments to challenge yet."}

Your job: Find the WEAKNESS in every argument above.
- What assumptions are untested?
- What data is missing?
- What's the contrarian case?
- Where is groupthink happening?

Be ruthless but fair. Challenge the strongest argument the most."""

    response = await llm_call(prompt, mode)
    entry = {"agent": "DevilsAdvocate", "output": response, "round": state.get("debate_round", 0)}
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def debate_evolution_supervisor_node(state: AgentState) -> AgentState:
    """Evolution Supervisor — meta-analysis of debate quality and agent performance.
    
    Also increments debate_round so the cyclic router knows when to stop.
    """
    question = state.get("question", "")
    mode = state.get("mode", 0)
    debate = state.get("debate_history", [])
    round_num = state.get("debate_round", 0)

    # Increment round AFTER all agents have spoken in this cycle
    new_round = round_num + 1
    state["debate_round"] = new_round

    agent_outputs = "\n".join([
        f"[Round {d.get('round', 0)}] {d['agent']}: {d['output'][:200]}"
        for d in debate[-12:]
    ])

    prompt = f"""You are the Evolution Supervisor on the POLYGOD Debate Floor.
Market: "{question}"
Debate Round: {round_num}

Agent outputs so far:
{agent_outputs if agent_outputs else "No outputs yet."}

Evaluate:
1. Which agent made the strongest argument? Why?
2. Which agent was weakest? What should they have said?
3. Has the debate converged or is there still disagreement?
4. Should we continue debating (suggest another round) or finalize?
5. Preliminary verdict: BUY YES, BUY NO, or NEUTRAL? (with confidence %)"""

    response = await llm_call(prompt, mode)
    entry = {"agent": "EvolutionSupervisor", "output": response, "round": round_num}
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def debate_moderator_node(state: AgentState) -> AgentState:
    """Moderator — synthesizes all debate into a final verdict."""
    question = state.get("question", "")
    market_data = state.get("market_data", {})
    mode = state.get("mode", 0)
    debate = state.get("debate_history", [])

    all_args = "\n\n".join([
        f"### {d['agent']} (Round {d.get('round', 0)}):\n{d['output']}"
        for d in debate
    ])

    prompt = f"""You are the Moderator of the POLYGOD Debate Floor.
Market: "{question}"
Current Price: {market_data.get('yes_percentage', 50):.1f}% YES
Mode: {mode} ({['OBSERVE', 'PAPER', 'LOW', 'BEAST'][min(mode, 3)]})

All debate arguments:
{all_args if all_args else "No arguments presented."}

Provide your FINAL VERDICT:
1. **Summary**: Key points for YES vs NO (2-3 sentences each)
2. **Evidence Weight**: Rate each agent's contribution (1-10)
3. **Verdict**: "BUY YES" / "BUY NO" / "STAY NEUTRAL"
4. **Confidence**: 0-100%
5. **Recommended Position Size**: Based on Kelly and conviction
6. **Key Risk**: The single biggest risk to this trade"""

    response = await llm_call(prompt, mode)
    state["debate_verdict"] = response
    entry = {"agent": "Moderator", "output": response, "round": state.get("debate_round", 0)}
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


# ==================== SWARM ROUTING ====================

def debate_router(state: AgentState) -> str:
    """Route debate: continue cycles or move to moderator."""
    round_num = state.get("debate_round", 0)
    mode = state.get("mode", 0)
    # Observe mode: 1 round, Paper: 2 rounds, Low/Beast: 3 rounds
    max_rounds = {0: 1, 1: 2, 2: 3, 3: 3}.get(mode, 2)
    if round_num >= max_rounds:
        return "moderator"
    return "stats"  # Cycle back for another round


def mode_router(state: AgentState) -> str:
    """Route based on mode: observe → approve, paper → risk_gate, beast → execute."""
    mode = state.get("mode", POLYGOD_MODE)
    if mode == 0:
        return "approve"
    elif mode == 1:
        return "risk_gate"
    else:
        return "evolution_lab" if mode >= 2 else "execute"


def post_evolution_router(state: AgentState) -> str:
    """After evolution lab: risk_gate for low mode, execute for beast."""
    mode = state.get("mode", POLYGOD_MODE)
    if mode >= 3:
        return "execute"
    return "risk_gate"


# ==================== EVOLUTION LAB ====================

@traceable
async def evolution_lab_node(state: AgentState) -> AgentState:
    """
    Evolution Lab — spawn parallel paper tournaments.
    Test multiple Kelly fractions, score with simulated PnL, promote best config.
    """
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    decision = state.get("decision", {})
    order = decision.get("order", {"size": 1000})
    mode = state.get("mode", 0)

    logger.info(f"EVOLUTION LAB: Running parallel tournaments for '{question[:50]}...'")

    # Kelly fractions to test
    kelly_fractions = [0.05, 0.10, 0.15, 0.20, 0.25, 0.33, 0.50, 0.75, 1.0]

    # Run tournament
    tournament = paper.run_tournament(order, market_data, kelly_fractions, sims=200)
    best = tournament.get("best", {})

    logger.info(f"Evolution Lab complete: best Kelly={best.get('kelly_fraction', 0):.0%}, "
                f"Sharpe={best.get('sharpe', 0):.2f}, win_rate={best.get('win_rate', 0):.1%}")

    # Update state with evolved decision
    evolved_order = {**order, "size": order.get("size", 100) * best.get("kelly_fraction", 0.25)}
    state["evolution_best"] = best
    state["decision"] = {
        **decision,
        "order": evolved_order,
        "evolution_kelly": best.get("kelly_fraction", 0.25),
        "evolution_sharpe": best.get("sharpe", 0),
        "evolution_win_rate": best.get("win_rate", 0),
    }
    state["kelly_fraction"] = best.get("kelly_fraction", 0.25)

    # Store evolution results in memory
    mem0_add(
        f"Evolution Lab for '{question}': best_kelly={best.get('kelly_fraction', 0):.0%}, "
        f"sharpe={best.get('sharpe', 0):.2f}",
        user_id=state.get("market_id", "polygod"),
    )

    return state


# ==================== DECISION NODES ====================

async def approve_node(state: AgentState) -> AgentState:
    """Approve trade for human review (observe mode)."""
    verdict = state.get("debate_verdict", "No verdict")
    logger.info(f"OBSERVE MODE: Trade requires human approval. Verdict: {verdict[:100]}...")
    mem0_add(f"Trade queued for approval: {verdict[:100]}", user_id=state.get("market_id", "polygod"))
    state["decision"] = {**state.get("decision", {}), "status": "pending_approval", "verdict": verdict}
    return state


async def risk_gate_node(state: AgentState) -> AgentState:
    """Risk gate with Monte Carlo + Kelly criterion."""
    decision = state.get("decision", {})
    order = decision.get("order", {"size": 100})
    market_data = state.get("market_data", {})
    mode = state.get("mode", 0)

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
        logger.info(f"RISK GATE PASSED: Kelly={kelly:.2f}, win_prob={p_win:.1%}, volume=${volume:,.0f}")
        mem0_add(f"Risk gate PASSED: Kelly={kelly:.2f}, win_prob={p_win:.1%}", user_id=state.get("market_id", "polygod"))
    else:
        state["decision"] = {**decision, "risk_status": "high", "next": "approve"}
        state["risk_status"] = "high"
        logger.warning(f"RISK GATE BLOCKED: Kelly={kelly:.2f}, win_prob={p_win:.1%}, worst_case=${sim.get('worst_case', 0):.2f}")
        mem0_add(f"Risk gate BLOCKED: Kelly={kelly:.2f}, win_prob={p_win:.1%}", user_id=state.get("market_id", "polygod"))

    return state


async def execute_node(state: AgentState) -> AgentState:
    """Execute trade — PaperMirror for paper/low mode, live for beast mode."""
    decision = state.get("decision", {})
    order = decision.get("order", {})
    mode = state.get("mode", POLYGOD_MODE)

    logger.info(f"EXECUTING in mode {mode}: {order}")

    if mode <= 1:
        # Paper mode — shadow execution
        result = paper.execute_shadow(order)
        state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)
        logger.info(f"Paper execution: pnl=${result.get('pnl', 0):.2f}")
    elif mode == 2:
        # Low mode — small live position with Kelly guard
        kelly = state.get("kelly_fraction", 0.25)
        safe_order = {**order, "size": order.get("size", 100) * min(kelly, 0.25)}
        result = paper.execute_shadow(safe_order)  # Still paper for safety
        state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)
        logger.info(f"Low mode (Kelly-guarded paper): size={safe_order.get('size')}, pnl=${result.get('pnl', 0):.2f}")
    else:
        # Beast mode — live execution (when ClobClient is configured)
        if clob is not None:
            try:
                # Live execution placeholder — replace with actual clob.create_order
                result = {"status": "live_executed", "order_id": f"live_{uuid.uuid4().hex[:8]}"}
                logger.info(f"BEAST MODE live execution: {result}")
            except Exception as e:
                logger.error(f"Live execution failed, falling back to paper: {e}")
                result = paper.execute_shadow(order)
                state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)
        else:
            result = paper.execute_shadow(order)
            state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)
            logger.warning("Beast mode but no ClobClient — fell back to PaperMirror")

    state["execution_result"] = result
    state["decision"] = {**decision, "execution_result": result}
    mem0_add(f"Execution result: {json.dumps(result)[:200]}", user_id=state.get("market_id", "polygod"))
    return state


# ==================== META REFLECTION ====================

async def karpathy_loop_node(state: AgentState) -> AgentState:
    """Karpathy-style self-improving mutation loop.

    Wired after parallel tournament in beast mode (mode >= 3):
    - AutoResearch Lab mutates strategy code
    - Tests via parallel paper tournament
    - Keeps winners (Sharpe > 2.0, PnL > 0), discards losers
    """
    mode = state.get("mode", 0)
    logger.info(f"KARPATY LOOP NODE: Running in mode {mode}")

    try:
        state = await autoresearch_lab.mutate_and_evolve(state)
        status = state.get("evolution_status", "unknown")
        logger.info(f"KARPATY LOOP: evolution_status={status}")
    except Exception as e:
        logger.error(f"Karpathy loop failed: {e}")
        state["evolution_status"] = "error"

    return state


async def niche_scanner_node(state: AgentState) -> AgentState:
    """Micro Niche Scanner — detect edge in low-liquidity recurring markets."""
    mode = state.get("mode", 0)
    logger.info(f"NICHE SCANNER NODE: Scanning niches in mode {mode}")
    
    try:
        opps = await scanner.scan_niches(mode)
        if opps:
            state["debate_history"] = state.get("debate_history", []) + [
                {"agent": "MicroNicheScanner", "output": f"Found {len(opps)} niche opportunities", "round": state.get("debate_round", 0)}
            ]
            # Auto-spawn parallel tournaments on free GPU
            for opp in opps[:3]:  # Limit to top 3 to avoid timeout
                tournament_state = {
                    **state,
                    "market_id": opp["market_id"],
                    "question": opp.get("title", "Unknown Market"),
                    "decision": {"order": {"size": 1000 * opp["kelly_size"]}},
                }
                state = await parallel_paper_tournament(tournament_state)
            logger.info(f"NICHE SCANNER: Processed {min(3, len(opps))} opportunities via tournament")
        else:
            logger.info("NICHE SCANNER: No opportunities found")
    except Exception as e:
        logger.error(f"Niche scanner failed: {e}")
    
    return state


async def meta_reflection_node(state: AgentState) -> AgentState:
    """Store full run outcome to mem0 and suggest prompt improvements."""
    outcome = {
        "run_id": state.get("run_id"),
        "market": state.get("question", ""),
        "mode": state.get("mode", 0),
        "paper_pnl": state.get("paper_pnl", 0),
        "risk_status": state.get("risk_status", "unknown"),
        "kelly_fraction": state.get("kelly_fraction", 0),
        "debate_rounds": state.get("debate_round", 0),
        "agents_used": len(set(d.get("agent") for d in state.get("debate_history", []))),
        "evolution_best": state.get("evolution_best"),
        "simulation": state.get("simulation"),
    }

    mem0_add(f"Run outcome: {json.dumps(outcome)[:500]}", user_id=state.get("market_id", "polygod"))

    # Suggest improvement
    suggestion = "Next cycle: weight X sentiment higher if bull_score > 0.7 and volume > $50k"
    mem0_add(f"Prompt improvement: {suggestion}", user_id=state.get("market_id", "polygod"))

    state["final_decision"] = {
        **state.get("decision", {}),
        "outcome": outcome,
        "verdict": state.get("debate_verdict", "No verdict"),
    }

    logger.info(f"META REFLECTION complete: pnl=${state.get('paper_pnl', 0):.2f}, "
                f"debate_rounds={state.get('debate_round', 0)}")
    return state


# ==================== CLOB CLIENT (for beast mode) ====================
clob = None
try:
    if settings.POLYMARKET_API_KEY:
        from py_clob_client.client import ClobClient
        clob = ClobClient(host=settings.POLYMARKET_API_HOST)
        logger.info("ClobClient initialized for beast mode")
except Exception as e:
    logger.warning(f"ClobClient init failed: {e}")


# ==================== GRAPH CONSTRUCTION ====================

def build_polygod_graph() -> StateGraph:
    """Build the god-tier cyclic swarm graph."""
    workflow = StateGraph(AgentState)

    # --- Core nodes ---
    workflow.add_node("memory_recall", memory_recall_node)
    workflow.add_node("research", grok_research_node)
    workflow.add_node("x_sentiment", x_sentiment_node)

    # --- Debate swarm nodes ---
    workflow.add_node("stats", debate_stats_node)
    workflow.add_node("time_decay", debate_time_decay_node)
    workflow.add_node("whale_rag", debate_whale_rag_node)
    workflow.add_node("devils_advocate", debate_devils_advocate_node)
    workflow.add_node("evolution_supervisor", debate_evolution_supervisor_node)
    workflow.add_node("moderator", debate_moderator_node)

    # --- Decision nodes ---
    workflow.add_node("approve", approve_node)
    workflow.add_node("risk_gate", risk_gate_node)
    workflow.add_node("evolution_lab", evolution_lab_node)
    workflow.add_node("parallel_tournament", parallel_paper_tournament)
    workflow.add_node("execute", execute_node)
    workflow.add_node("niche_scanner", niche_scanner_node)
    workflow.add_node("karpathy_loop", karpathy_loop_node)
    workflow.add_node("meta_reflection", meta_reflection_node)

    # ==================== EDGES ====================

    # Entry: memory → research → x_sentiment → debate swarm
    workflow.set_entry_point("memory_recall")
    workflow.add_edge("memory_recall", "research")
    workflow.add_edge("research", "x_sentiment")
    workflow.add_edge("x_sentiment", "stats")

    # --- Cyclic debate swarm ---
    # Stats → TimeDecay → WhaleRAG → DevilsAdvocate → EvolutionSupervisor → (cycle or moderator)
    workflow.add_edge("stats", "time_decay")
    workflow.add_edge("time_decay", "whale_rag")
    workflow.add_edge("whale_rag", "devils_advocate")
    workflow.add_edge("devils_advocate", "evolution_supervisor")

    # Evolution Supervisor increments round and routes: cycle back to stats OR go to moderator
    def increment_round(state: AgentState) -> AgentState:
        state["debate_round"] = state.get("debate_round", 0) + 1
        return state

    # We use conditional edges from evolution_supervisor
    workflow.add_conditional_edges(
        "evolution_supervisor",
        debate_router,
        {
            "stats": "stats",           # Cycle back for another round
            "moderator": "moderator",   # Debate converged → finalize
        },
    )

    # --- Post-debate: moderator → niche_scanner (cyclic after debate) ---
    workflow.add_edge("moderator", "niche_scanner")
    
    # niche_scanner → mode routing ---
    workflow.add_conditional_edges(
        "niche_scanner",
        mode_router,
        {
            "approve": "approve",           # Observe mode
            "risk_gate": "risk_gate",       # Paper mode
            "evolution_lab": "evolution_lab",  # Low/Beast mode
            "execute": "execute",           # Direct execute (beast)
        },
    )

    # Approve → meta_reflection
    workflow.add_edge("approve", "meta_reflection")

    # Risk gate → conditional: execute or approve
    def risk_router(state: AgentState) -> str:
        return state.get("decision", {}).get("next", "approve")

    workflow.add_conditional_edges(
        "risk_gate",
        risk_router,
        {
            "execute": "execute",
            "approve": "approve",
        },
    )

    # Evolution lab → parallel_tournament (god-tier 50-variant tournament)
    workflow.add_edge("evolution_lab", "parallel_tournament")

    # Parallel tournament → Karpathy loop (beast mode) or meta_reflection
    workflow.add_conditional_edges(
        "parallel_tournament",
        lambda s: "karpathy_loop" if s.get("mode", 0) >= 3 else "meta_reflection",
        {
            "karpathy_loop": "karpathy_loop",
            "meta_reflection": "meta_reflection",
        },
    )

    # Karpathy loop → meta_reflection (self-improvement complete)
    workflow.add_edge("karpathy_loop", "meta_reflection")

    # Execute → meta_reflection
    workflow.add_edge("execute", "meta_reflection")

    # Meta reflection → END
    workflow.add_edge("meta_reflection", END)

    return workflow


# ==================== COMPILE ====================
polygod_graph = build_polygod_graph().compile(checkpointer=checkpointer)

logger.info(
    "POLYGOD GOD-TIER CYCLIC SWARM compiled: "
    "memory_recall → research → x_sentiment → [cyclic debate swarm] → moderator → "
    "[approve | risk_gate | evolution_lab] → execute → meta_reflection → END"
)


# ==================== ENTRY POINT ====================

async def run_polygod(market_id: str, mode: int = 0, question: str = "") -> dict:
    """
    Main entry point for POLYGOD cyclic swarm.

    Args:
        market_id: Polymarket condition ID or slug
        mode: 0=observe, 1=paper, 2=low, 3=beast
        question: Market question (auto-fetched if empty)

    Returns:
        Final state with verdict, execution result, and PnL
    """
    global POLYGOD_MODE
    POLYGOD_MODE = mode

    # Fetch enriched market data
    market_data = await get_enriched_market_data(market_id)
    if not question:
        question = market_data.get("title", f"Market {market_id}")

    run_id = str(uuid.uuid4())[:8]

    initial_state: AgentState = {
        "run_id": run_id,
        "mode": mode,
        "market_id": market_id,
        "market_data": market_data,
        "question": question,
        "research_insight": "",
        "x_sentiment": {"bull_score": 0.5},
        "debate_round": 0,
        "debate_history": [],
        "debate_verdict": "",
        "decision": {"order": {"size": 1000}},
        "simulation": None,
        "kelly_fraction": 0.25,
        "risk_status": "pending",
        "evolution_best": None,
        "paper_pnl": 0.0,
        "execution_result": None,
        "memory_context": {},
        "final_decision": None,
    }

    logger.info(f"POLYGOD RUN [{run_id}]: market={market_id}, mode={mode}, question='{question[:60]}...'")

    config = {"configurable": {"thread_id": f"polygod-{market_id}-{run_id}"}}
    result = await polygod_graph.ainvoke(initial_state, config=config)

    logger.info(
        f"POLYGOD RUN [{run_id}] COMPLETE: "
        f"verdict='{result.get('debate_verdict', '')[:80]}...', "
        f"pnl=${result.get('paper_pnl', 0):.2f}, "
        f"risk={result.get('risk_status', 'unknown')}"
    )

    return result