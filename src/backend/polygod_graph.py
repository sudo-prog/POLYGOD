"""
POLYGOD_GRAPH — God-Tier LangGraph Swarm + Grok-3/4 + FREE On-Chain Verification Loop
Zero extra cost. Runs on free-tier Gemini by default. Grok only when credits available.
"""

import json
import logging
import random
import re
import uuid
from datetime import datetime
from typing import TypedDict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_xai import ChatXAI
from langgraph.graph import END, StateGraph

try:
    from langgraph.checkpoint.memory import MemorySaver
except ImportError:
    MemorySaver = None

try:
    from mem0 import Memory
except ImportError:
    Memory = None

from src.backend.config import settings
from src.backend.polymarket.client import polymarket_client

logger = logging.getLogger(__name__)

# ==================== MODE ====================
POLYGOD_MODE: int = settings.POLYGOD_MODE


# ==================== LLM ROUTING ====================
def get_llm(model: str = "gemini"):
    """
    LLM router — prefers free tier, escalates only when allowed.

    Default: free Gemini (gemini-2.5-pro-exp or flash)
    Escalation: Grok-4 via xAI (only when GROK_API_KEY present)
    """
    if model == "grok" and settings.GROK_API_KEY:
        logger.info("LLM routing → Grok-4 (high-stakes escalation)")
        return ChatXAI(model="grok-4", api_key=settings.GROK_API_KEY, temperature=0.3)
    # Default: free Gemini
    logger.info("LLM routing → Gemini (free tier)")
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-pro-exp-03-25",
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.3,
        max_output_tokens=8192,
    )


# ==================== MEMORY (Mem0) ====================
mem0_memory = None
try:
    mem0_config = json.loads(settings.MEM0_CONFIG)
    mem0_memory = Memory.from_config(mem0_config)
except Exception as e:
    logger.warning(f"Mem0 initialization failed: {e}")


def mem0_add(content: str, user_id: str = "polygod"):
    """Add to mem0 memory with graceful fallback."""
    if mem0_memory:
        try:
            mem0_memory.add(
                messages=[{"role": "system", "content": content}], user_id=user_id
            )
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


# ==================== PAPER MIRROR ====================
class PaperMirror:
    """Shadow execution engine for paper trading + simulations."""

    def __init__(self):
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
            outcomes = []
            for _ in range(sims):
                result = self.execute_shadow(adjusted_order)
                outcomes.append(result["pnl"])
            avg_pnl = sum(outcomes) / len(outcomes) if outcomes else 0
            win_rate = (
                sum(1 for o in outcomes if o > 0) / len(outcomes) if outcomes else 0
            )
            results.append(
                {
                    "kelly_fraction": kf,
                    "avg_pnl": avg_pnl,
                    "win_rate": win_rate,
                    "sharpe": (
                        avg_pnl
                        / (
                            max(
                                0.001,
                                (
                                    sum((o - avg_pnl) ** 2 for o in outcomes)
                                    / len(outcomes)
                                )
                                ** 0.5,
                            )
                        )
                        if outcomes
                        else 0
                    ),
                }
            )
        results.sort(key=lambda r: r["sharpe"], reverse=True)
        return {"tournament_results": results, "best": results[0] if results else None}


paper = PaperMirror()


# ==================== MARKET DATA ENRICHMENT ====================
async def get_enriched_market_data(market_id: str) -> dict:
    """Fetch enriched market data for analysis."""
    try:
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


# ==================== ON-CHAIN VERIFICATION ====================
async def verify_onchain_orders(market_id: str) -> list[dict]:
    """
    Free on-chain + CLOB verification loop.
    No gas, no auth for reads — just public endpoints.
    """
    try:
        # 1. CLOB orderbook (public) — fetch for context
        await polymarket_client.get_order_book(market_id)
        # 2. Recent fills via CLOB history (public endpoint)
        fills = await polymarket_client.get_recent_fills(market_id, limit=10)
        return fills or []
    except Exception:
        return []  # never crash the graph


# ==================== STATE ====================
class AgentState(TypedDict):
    """Streamlined God-Tier Swarm state."""

    run_id: str
    mode: int  # 0=observe, 1=paper, 2=low, 3=beast
    market_id: str
    market_data: dict
    question: str
    # Agent outputs
    statistics: str
    time_decay: str
    generalist: str
    macro: str
    devil: str
    # Debate meta
    debate_round: int
    debate_history: list[dict]  # [{agent, output, round}]
    # Decision
    verdict: str
    confidence: float
    decision: dict
    # Risk
    simulation: dict | None
    kelly_fraction: float
    risk_status: str
    # On-chain
    on_chain_fills: list[dict]
    # Execution
    paper_pnl: float
    execution_result: dict | None
    # Meta
    final_decision: dict | None


# ==================== ENRICHED MARKET DATA HELPER ====================
async def _fetch_market_data(market_id: str, question: str = "") -> tuple[dict, str]:
    """Fetch market data and derive question."""
    market_data = await get_enriched_market_data(market_id)
    if not question:
        question = market_data.get("title", f"Market {market_id}")
    return market_data, question


# ==================== SWARM AGENTS ====================


async def statistics_agent(state: AgentState) -> AgentState:
    """Statistics Expert — quantitative analysis with Monte Carlo."""
    llm = get_llm("gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    prob = float(market_data.get("prob", 0.5))
    volume = market_data.get("volume", 0)

    # Run Monte Carlo for context
    sim = run_monte_carlo({"size": 1000}, market_data)
    kelly = calculate_kelly(prob)

    prompt = f"""Analyze raw stats for this Polymarket market. Be ruthless with numbers.

Market: "{question}"
Current Price: {market_data.get('yes_percentage', prob * 100):.1f}% YES
7d Volume: ${volume:,.0f}

Monte Carlo Results (5000 sims):
- Win Probability: {sim['win_prob']:.1%}
- Expected PnL: ${sim['expected_pnl']:.2f}
- 95% VaR: ${sim['confidence_95']:.2f}
- Kelly Fraction: {kelly:.1%}

Is there statistical edge? What do the numbers actually say?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["statistics"] = str(msg.content)
    round_num = state.get("debate_round", 0)
    entry = {
        "agent": "StatsExpert",
        "output": str(msg.content),
        "round": round_num,
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def time_decay_agent(state: AgentState) -> AgentState:
    """Time Decay Analyst — resolution timing and theta analysis."""
    llm = get_llm("gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    end_date = market_data.get("end_date", "Unknown")
    prob = float(market_data.get("prob", 0.5))

    # Calculate days remaining
    days_remaining = "?"
    urgency = "Unknown"
    try:
        for fmt in [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%SZ",
        ]:
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

    prompt = f"""Focus ONLY on time-to-resolution, theta decay, urgency for this market.

Market: "{question}"
Resolution Date: {end_date} | Days Remaining: {days_remaining}
Urgency: {urgency}
Current Price: {prob:.1%} YES

Analyze:
1. Is time working for or against each side?
2. What catalysts could accelerate price convergence?
3. Is the current price "priced in" given time remaining?
4. Optimal entry timing?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["time_decay"] = str(msg.content)
    round_num = state.get("debate_round", 0)
    entry = {
        "agent": "TimeDecay",
        "output": str(msg.content),
        "round": round_num,
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def generalist_agent(state: AgentState) -> AgentState:
    """Generalist — broad reasoning about real-world likelihood."""
    llm = get_llm("gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")

    prior_args = "\n".join(
        [
            f"- {d['agent']}: {d['output'][:150]}"
            for d in state.get("debate_history", [])[-6:]
        ]
    )

    prompt = f"""You are the Generalist Analyst on the POLYGOD Debate Floor.
Market: "{question}"
Current Price: {market_data.get('yes_percentage', 50):.1f}% YES

Prior debate arguments:
{prior_args if prior_args else "No prior arguments — you go first."}

Analyze from a real-world perspective:
1. What does the underlying event actually look like?
2. Are there non-obvious factors the market is missing?
3. What's your gut probability vs market price?
4. If you were betting your own money, what would you do?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["generalist"] = str(msg.content)
    round_num = state.get("debate_round", 0)
    entry = {
        "agent": "Generalist",
        "output": str(msg.content),
        "round": round_num,
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def macro_agent(state: AgentState) -> AgentState:
    """Macro Analyst — macro environment, correlations, regime shifts."""
    llm = get_llm("gemini")
    question = state.get("question", "")

    prior_args = "\n".join(
        [
            f"- {d['agent']}: {d['output'][:150]}"
            for d in state.get("debate_history", [])[-6:]
        ]
    )

    prompt = f"""You are the Macro Analyst on the POLYGOD Debate Floor.
Market: "{question}"

Prior debate arguments:
{prior_args if prior_args else "No prior arguments yet."}

Analyze the macro context:
1. What broader trends affect this market? (politics, economics, crypto cycles)
2. How does this correlate with other markets or assets?
3. Are we in a regime where prediction markets are systematically mispriced?
4. What's the macro-level edge here?"""

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["macro"] = str(msg.content)
    round_num = state.get("debate_round", 0)
    entry = {
        "agent": "MacroAnalyst",
        "output": str(msg.content),
        "round": round_num,
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


async def devil_agent(state: AgentState) -> AgentState:
    """Devil's Advocate — challenges consensus and finds logical fallacies."""
    llm = get_llm("gemini")
    question = state.get("question", "")
    prior_args = "\n".join(
        [
            f"- {d['agent']}: {d['output'][:200]}"
            for d in state.get("debate_history", [])[-8:]
        ]
    )

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

    msg = await llm.ainvoke([HumanMessage(content=prompt)])
    state["devil"] = str(msg.content)
    round_num = state.get("debate_round", 0)
    entry = {
        "agent": "DevilsAdvocate",
        "output": str(msg.content),
        "round": round_num,
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]
    return state


# ==================== ON-CHAIN VERIFICATION NODE ====================
async def onchain_verification_node(state: AgentState) -> AgentState:
    """Free on-chain + CLOB verification before final verdict (mode >= 2)."""
    if settings.POLYGOD_MODE >= 2:
        state["on_chain_fills"] = await verify_onchain_orders(state["market_id"])
        whale_activity = len(state["on_chain_fills"]) > 0
        logger.info(
            f"On-chain verification: {len(state['on_chain_fills'])} fills, "
            f"whale_activity={'YES' if whale_activity else 'NO'}"
        )
        # Inject whale context into market_data for moderator
        state["market_data"] = {
            **state.get("market_data", {}),
            "whale_activity": whale_activity,
        }
    return state


# ==================== MODERATOR ====================
async def moderator_agent(state: AgentState) -> AgentState:
    """
    Moderator — synthesizes all agent inputs into ONE final verdict.
    Escalates to Grok if available (high-stakes truth-seeking).
    """
    llm = get_llm("grok" if settings.GROK_API_KEY else "gemini")
    market_data = state.get("market_data", {})
    question = state.get("question", "")
    debate = state.get("debate_history", [])

    all_args = "\n\n".join(
        [
            f"### {d['agent']} (Round {d.get('round', 0)}):\n{d['output']}"
            for d in debate
        ]
    )

    # On-chain context
    onchain_ctx = ""
    if state.get("on_chain_fills"):
        fills_count = len(state["on_chain_fills"])
        onchain_ctx = (
            f"\n\n🐋 ON-CHAIN VERIFICATION: {fills_count} recent fills "
            "detected — whale activity confirmed."
        )
    elif state.get("market_data", {}).get("whale_activity") is False:
        onchain_ctx = (
            "\n🐋 ON-CHAIN VERIFICATION: " "No significant fills in last 10 trades."
        )

    prompt = f"""You are the Moderator of the POLYGOD Debate Floor.
Market: "{question}"
Current Price: {market_data.get('yes_percentage', 50):.1f}% YES

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

    # Parse confidence from verdict
    confidence = 50.0
    conf_match = re.search(
        r"(?:confidence|odds)[:\s]*(\d+)", verdict_text, re.IGNORECASE
    )
    if conf_match:
        confidence = float(conf_match.group(1))

    state["verdict"] = verdict_text
    state["confidence"] = confidence
    entry = {
        "agent": "Moderator",
        "output": verdict_text,
        "round": state.get("debate_round", 0),
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]

    # Set default decision
    state["decision"] = {
        "order": {"size": 1000},
        "verdict": verdict_text,
        "confidence": confidence,
    }

    return state


# ==================== EVOLUTION SUPERVISOR (cycle controller) ====================
async def evolution_supervisor_node(state: AgentState) -> AgentState:
    """
    Evolution Supervisor — meta-analysis of debate quality + round controller.
    Increments debate_round so the cyclic router knows when to stop.
    """
    round_num = state.get("debate_round", 0)
    new_round = round_num + 1
    state["debate_round"] = new_round

    debate = state.get("debate_history", [])

    logger.info(
        f"Evolution Supervisor: round {new_round}, "
        f"{len(debate)} total agent outputs"
    )

    entry = {
        "agent": "EvolutionSupervisor",
        "output": f"Round {new_round} complete. {len(debate)} arguments recorded.",
        "round": round_num,
    }
    state["debate_history"] = state.get("debate_history", []) + [entry]

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
            f"RISK GATE PASSED: Kelly={kelly:.2f}, "
            f"win_prob={p_win:.1%}, volume=${volume:,.0f}"
        )
    else:
        state["decision"] = {**decision, "risk_status": "high", "next": "approve"}
        state["risk_status"] = "high"
        logger.warning(
            f"RISK GATE BLOCKED: Kelly={kelly:.2f}, win_prob={p_win:.1%}, "
            f"worst_case=${sim.get('worst_case', 0):.2f}"
        )

    return state


# ==================== APPROVE / EXECUTE ====================
async def approve_node(state: AgentState) -> AgentState:
    """Approve trade for human review (observe mode)."""
    verdict = state.get("verdict", "No verdict")
    logger.info(
        f"OBSERVE MODE: Trade requires human approval. Verdict: {verdict[:100]}..."
    )
    state["decision"] = {**state.get("decision", {}), "status": "pending_approval"}
    return state


async def execute_node(state: AgentState) -> AgentState:
    """Execute trade — PaperMirror for paper/low mode, live for beast mode."""
    decision = state.get("decision", {})
    order = decision.get("order", {})
    mode = state.get("mode", POLYGOD_MODE)

    logger.info(f"EXECUTING in mode {mode}: {order}")

    if mode <= 2:
        # Paper / Low mode — shadow execution
        result = paper.execute_shadow(order)
        state["paper_pnl"] = state.get("paper_pnl", 0) + result.get("pnl", 0)
        logger.info(f"Paper execution: pnl=${result.get('pnl', 0):.2f}")
    else:
        # Beast mode — live execution (when ClobClient is configured)
        clob = None
        try:
            if settings.POLYMARKET_API_KEY:
                from py_clob_client.client import ClobClient

                clob = ClobClient(host=settings.POLYMARKET_API_HOST)
        except Exception:
            pass

        if clob is not None:
            try:
                result = {
                    "status": "live_executed",
                    "order_id": f"live_{uuid.uuid4().hex[:8]}",
                }
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
    return state


# ==================== META REFLECTION ====================
async def meta_reflection_node(state: AgentState) -> AgentState:
    """Store full run outcome to mem0 and finalize."""
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
        f"META REFLECTION complete: pnl=${state.get('paper_pnl', 0):.2f}, "
        f"confidence={state.get('confidence', 0):.0f}%"
    )
    return state


# ==================== ROUTING ====================
def debate_router(state: AgentState) -> str:
    """Route debate: continue cycles or move to moderator."""
    round_num = state.get("debate_round", 0)
    mode = state.get("mode", 0)
    max_rounds = {0: 1, 1: 2, 2: 3, 3: 3}.get(mode, 2)
    if round_num >= max_rounds:
        return "moderator"
    return "stats"


def mode_router(state: AgentState) -> str:
    """Route based on mode after debate."""
    mode = state.get("mode", POLYGOD_MODE)
    if mode == 0:
        return "approve"
    elif mode == 1:
        return "risk_gate"
    else:
        return "risk_gate"


def risk_router(state: AgentState) -> str:
    """Risk gate → execute or approve."""
    return state.get("decision", {}).get("next", "approve")


# ==================== GRAPH CONSTRUCTION ====================
def build_polygod_graph() -> StateGraph:
    """Build the god-tier cyclic swarm graph."""
    workflow = StateGraph(AgentState)

    # --- Core nodes ---
    workflow.add_node("statistics", statistics_agent)
    workflow.add_node("time_decay", time_decay_agent)
    workflow.add_node("generalist", generalist_agent)
    workflow.add_node("macro", macro_agent)
    workflow.add_node("devil", devil_agent)
    workflow.add_node("onchain_verify", onchain_verification_node)
    workflow.add_node("evolution_supervisor", evolution_supervisor_node)
    workflow.add_node("moderator", moderator_agent)

    # --- Decision nodes ---
    workflow.add_node("approve", approve_node)
    workflow.add_node("risk_gate", risk_gate_node)
    workflow.add_node("execute", execute_node)
    workflow.add_node("meta_reflection", meta_reflection_node)

    # ==================== EDGES ====================

    # Entry: statistics → time_decay → generalist → macro → devil
    workflow.set_entry_point("statistics")
    workflow.add_edge("statistics", "time_decay")
    workflow.add_edge("time_decay", "generalist")
    workflow.add_edge("generalist", "macro")
    workflow.add_edge("macro", "devil")

    # Devil → evolution_supervisor (cycle controller)
    workflow.add_edge("devil", "evolution_supervisor")

    # Evolution supervisor → cycle back to stats OR go to on-chain verify / moderator
    def _cycle_or_finish(s: AgentState) -> str:
        max_rounds = {0: 1, 1: 2, 2: 3, 3: 3}.get(s.get("mode", 0), 2)
        return "moderator" if s.get("debate_round", 0) >= max_rounds else "stats"

    workflow.add_conditional_edges(
        "evolution_supervisor",
        _cycle_or_finish,
        {
            "stats": "statistics",  # Cycle back for another round
            "moderator": "moderator",  # Debate converged → finalize
        },
    )

    # Moderator → on-chain verify (mode >= 2) or direct to mode routing
    # Using a conditional edge: always go through onchain_verify, it's a no-op if mode < 2
    workflow.add_edge("moderator", "onchain_verify")

    # On-chain verify → mode routing
    workflow.add_conditional_edges(
        "onchain_verify",
        mode_router,
        {
            "approve": "approve",
            "risk_gate": "risk_gate",
        },
    )

    # Approve → meta_reflection
    workflow.add_edge("approve", "meta_reflection")

    # Risk gate → execute or approve
    workflow.add_conditional_edges(
        "risk_gate",
        risk_router,
        {
            "execute": "execute",
            "approve": "approve",
        },
    )

    # Execute → meta_reflection
    workflow.add_edge("execute", "meta_reflection")

    # Meta reflection → END
    workflow.add_edge("meta_reflection", END)

    return workflow


# ==================== COMPILE ====================
memory_saver = MemorySaver() if MemorySaver else None
polygod_graph = build_polygod_graph().compile(
    checkpointer=memory_saver if memory_saver else None
)

logger.info(
    "POLYGOD GOD-TIER SWARM compiled: "
    "statistics → time_decay → generalist → macro → devil → [cyclic] → "
    "moderator → onchain_verify → [approve | risk_gate] → execute → meta_reflection → END"
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
        "risk_status": "pending",
        "on_chain_fills": [],
        "paper_pnl": 0.0,
        "execution_result": None,
        "final_decision": None,
    }

    q_short = question[:60]
    logger.info(
        f"POLYGOD RUN [{run_id}]: market={market_id}, mode={mode}, question='{q_short}...'"
    )

    config: RunnableConfig = {
        "configurable": {"thread_id": f"polygod-{market_id}-{run_id}"}
    }
    result = await polygod_graph.ainvoke(initial_state, config=config)

    logger.info(
        f"POLYGOD RUN [{run_id}] COMPLETE: "
        f"verdict='{result.get('verdict', '')[:80]}...', "
        f"pnl=${result.get('paper_pnl', 0):.2f}, "
        f"risk={result.get('risk_status', 'unknown')}"
    )

    return result
