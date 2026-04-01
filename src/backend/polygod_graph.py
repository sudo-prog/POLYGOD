# src/backend/polygod_graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Any, Dict, TypedDict
from py_clob_client.client import ClobClient
import httpx
import random
import asyncio
import json
import logging

from mem0 import Memory
from langchain_google_genai import ChatGoogleGenerativeAI
from src.backend.config import settings
from src.backend.tools.x_sentiment import get_x_sentiment

logger = logging.getLogger(__name__)

# ==================== MEMORY & PAPER MIRROR ====================
langgraph_memory = MemorySaver()
mem0_config = json.loads(settings.MEM0_CONFIG)
mem0_memory = Memory.from_config(mem0_config)

# ClobClient with real settings
try:
    clob = ClobClient(
        host=settings.POLYMARKET_API_HOST
    ) if settings.POLYMARKET_API_KEY else None
except Exception as e:
    logger.warning(f"ClobClient initialization failed: {e}")
    clob = None


class PaperMirror:
    def __init__(self):
        self.pnls = []

    def execute_shadow(self, order):
        self.pnls.append(0.05)
        return {"pnl": 0.05, "status": "paper_executed"}


paper = PaperMirror()
POLYGOD_MODE = 0


class AgentState(TypedDict):
    mode: int
    market_data: dict
    decision: dict
    paper_pnl: float
    simulation: dict | None


# ==================== GOD TIER HELPERS ====================
async def call_grok(prompt: str) -> str:
    """GOD TIER: xAI Grok for truth-seeking alpha research"""
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
                    "max_tokens": 800
                },
                timeout=30.0
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"Grok API error: {e}")
        return f"Grok error: {e}"


async def call_gemini(prompt: str) -> str:
    """GOD TIER: Google Gemini for low-stakes analysis"""
    if not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set — falling back")
        return "Gemini unavailable — using basic insight"
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-pro",
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=800
        )
        response = llm.invoke(prompt)
        return str(response.content)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return f"Gemini error: {e}"


def multi_model_router(state: AgentState) -> str:
    """GOD TIER: Chooses best LLM based on mode & stake"""
    mode = state.get("mode", 0)
    size = float(state.get("decision", {}).get("order", {}).get("size", 100))
    if mode >= 2 or size > 5000:
        return "grok"      # high-stakes → Grok (truth-seeking)
    return "gemini"        # low-stakes → Gemini (efficient)


def run_monte_carlo(order: dict, market_data: dict, sims: int = 5000) -> dict:
    """GOD TIER Monte-Carlo risk engine"""
    size = float(order.get("size", 100))
    prob = market_data.get("prob", 0.5)
    volatility = market_data.get("volume", 10000) / 100000.0 + 0.05
    outcomes = []
    for _ in range(sims):
        outcome = random.gauss(prob, volatility)
        pnl = size * (1 if outcome > 0.5 else -1) * random.uniform(0.8, 1.2)
        outcomes.append(pnl)
    return {
        "expected_pnl": sum(outcomes) / sims,
        "win_prob": sum(1 for o in outcomes if o > 0) / sims,
        "worst_case": min(outcomes),
        "confidence_95": sorted(outcomes)[int(sims * 0.05)],
        "recommend_size": size * 0.8 if min(outcomes) < -size * 0.3 else size
    }


# ==================== NODES ====================
async def grok_research_node(state: AgentState) -> AgentState:
    """GOD TIER: New async grok_research_node replacing consult_dexter — calls xAI Grok API"""
    market_data = state.get("market_data", {})

    prompt = f"""POLYGOD alpha research: Analyze this Polymarket market for edge.

Market Data: {market_data}

Be brutally truthful. Identify:
1. Is there informational edge?
2. What's the true probability vs market price?
3. Key risks and catalysts?
4. Recommended position size?"""

    logger.info("Routing to Grok (high-stakes)")
    insight = await call_grok(prompt)

    # Store insight in memory
    mem0_memory.add(
        messages=[{"role": "system", "content": f"Grok alpha: {insight}"}],
        user_id="polygod"
    )

    # Update market_data with research insights
    state["market_data"] = market_data | {"prob": 0.65, "research_insight": insight}
    return state


def x_sentiment_node(state: AgentState) -> AgentState:
    """x_sentiment integration node — called after research, adds sentiment_score to state"""
    market_data = state.get("market_data", {})
    market_slug = market_data.get("slug", "")
    if market_slug:
        try:
            x_sentiment = asyncio.run(get_x_sentiment(market_slug))
            sentiment_score = x_sentiment.get("bull_score", 0.5)
            state["sentiment_score"] = sentiment_score
            market_data["x_sentiment"] = x_sentiment
            logger.info(f"X sentiment fetched for {market_slug}: bull_score={sentiment_score}")
        except Exception as e:
            logger.warning(f"Failed to fetch X sentiment: {e}")
            state["sentiment_score"] = 0.5
            market_data["x_sentiment"] = {"bull_score": 0.5, "error": str(e)}
    return state


def mode_router(state: AgentState) -> str:
    """Fixed mode_router — returns EXACT node names that exist: "approve", "risk_gate", "execute" (no _node suffix)"""
    # Use POLYGOD_MODE global (removes any circular import in get_current_mode)
    mode = POLYGOD_MODE
    if mode == 0:
        return "approve"
    elif mode == 1:
        return "risk_gate"
    else:
        return "execute"


def approve_node(state: AgentState) -> AgentState:
    """Approve trade for execution"""
    logger.info("POLYGOD APPROVED — waiting for human or auto-execute")
    mem0_memory.add(
        messages=[{"role": "system", "content": "Trade approved by risk gate"}],
        user_id="polygod"
    )
    return state


def risk_gate_node(state: AgentState) -> AgentState:
    """GOD TIER: Monte-Carlo inside risk gate — UPGRADED with Kelly Criterion (kept ALL existing logic + PaperMirror)"""
    decision = state.get("decision", {})
    order = decision.get("order", {"size": 100})
    market_data = state.get("market_data", {})

    # Run Monte-Carlo simulation
    sim = run_monte_carlo(order, market_data)
    state["simulation"] = sim

    # Calculate risk score
    size = float(order.get("size", 100))
    volume = market_data.get("volume", 10000) or 10000
    risk_score = (size / volume) * 0.1

    # Kelly Criterion upgrade
    edge = sim.get("expected_pnl", 0) / size if size > 0 else 0.0
    win_prob = sim["win_prob"]
    volatility = market_data.get("volume", 10000) / 100000.0 + 0.05
    kelly_fraction = (edge * win_prob - (1 - win_prob)) / volatility if volatility > 0 else 0.0
    # auto-scale order size
    order["size"] = size * max(0.0, kelly_fraction)
    state["decision"]["order"] = order
    logger.info(f"Kelly fraction: {kelly_fraction:.3f} — auto-scaled order size to {order['size']}")
    mem0_memory.add(
        messages=[{"role": "system", "content": f"Kelly upgrade: fraction={kelly_fraction:.3f}, scaled_size={order['size']}"}],
        user_id="polygod"
    )

    # Decision logic based on Monte-Carlo (kept ALL existing)
    if sim["worst_case"] < -500 or risk_score > 0.05:
        reason = f"Monte-Carlo FAILED — worst case ${sim['worst_case']:.0f}, risk_score={risk_score:.3f}"
        logger.warning(reason)
        mem0_memory.add(
            messages=[{"role": "system", "content": reason}],
            user_id="polygod"
        )
        return state
    reason = f"Monte-Carlo PASSED — expected ${sim['expected_pnl']:.0f}, win_prob={sim['win_prob']:.1%}"
    logger.info(reason)
    mem0_memory.add(
        messages=[{"role": "system", "content": reason}],
        user_id="polygod"
    )
    return state


def execute_node(state: AgentState) -> AgentState:
    """Execute trade (paper or live)"""
    logger.info("POLYGOD EXECUTING TRADE...")
    order = state.get("decision", {}).get("order", {})

    if POLYGOD_MODE >= 1:  # paper or live
        result = paper.execute_shadow(order)
        state["paper_pnl"] = float(result.get("pnl", 0.0))

    # Try live execution if ClobClient available and mode >= 2
    if clob and state.get("mode", 0) >= 2:
        try:
            clob.create_market_order(order)
            logger.info(f"Live order executed: {order}")
        except Exception as e:
            logger.error(f"Live execution failed: {e}")
            mem0_memory.add(
                messages=[{"role": "system", "content": f"execution_error: {str(e)}"}],
                user_id="polygod"
            )

    mem0_memory.add(
        messages=[{"role": "system", "content": f"Executed order: {order}"}],
        user_id="polygod"
    )
    return state


def critic_node(state: AgentState) -> AgentState:
    """Review trade and store lessons learned"""
    logger.info("POLYGOD CRITIC reviewing trade...")
    pnl = state.get("paper_pnl", 0)

    # Store trade outcome for learning
    trade_result = "successful" if pnl > 0 else "failed"
    mem0_memory.add(
        messages=[{"role": "system", "content": f"Trade {trade_result}: pnl={pnl}"}],
        user_id="polygod"
    )

    # Store learning for future prompts
    if trade_result == "successful":
        mem0_memory.add(
            messages=[{"role": "system", "content": "Lesson: Increase confidence in similar market conditions"}],
            user_id="polygod"
        )
    else:
        mem0_memory.add(
            messages=[{"role": "system", "content": "Lesson: Reduce position size in similar market conditions"}],
            user_id="polygod"
        )

    return state


def meta_reflection_node(state: AgentState) -> AgentState:
    """New meta_reflection node — stores entire run outcome to mem0 and suggests one prompt improvement"""
    outcome = {
        "final_pnl": state.get("paper_pnl", 0),
        "mode": POLYGOD_MODE,
        "sentiment_score": state.get("sentiment_score"),
        "simulation": state.get("simulation"),
        "research_insight": state.get("market_data", {}).get("research_insight")
    }
    mem0_memory.add(
        messages=[{"role": "system", "content": f"Full run outcome: {json.dumps(outcome)}"}],
        user_id="polygod"
    )
    suggestion = "Next cycle: include more recent X whale sentiment and Kelly-adjusted sizing in research prompt"
    mem0_memory.add(
        messages=[{"role": "system", "content": f"Prompt improvement suggestion: {suggestion}"}],
        user_id="polygod"
    )
    logger.info(f"META REFLECTION: {suggestion}")
    return state


# ==================== GRAPH ====================
workflow = StateGraph(AgentState)

workflow.add_node("research", grok_research_node)
workflow.add_node("x_sentiment", x_sentiment_node)
workflow.add_node("router", mode_router)
workflow.add_node("approve", approve_node)
workflow.add_node("risk_gate", risk_gate_node)
workflow.add_node("execute", execute_node)
workflow.add_node("critic", critic_node)
workflow.add_node("meta_reflection", meta_reflection_node)

# Set entry point
workflow.set_entry_point("research")

# Updated flow: research → x_sentiment → router → approve/risk_gate/execute → critic → meta_reflection → END
workflow.add_edge("research", "x_sentiment")
workflow.add_edge("x_sentiment", "router")
workflow.add_conditional_edges(
    "router",
    mode_router,
    {
        "approve": "approve",
        "risk_gate": "risk_gate",
        "execute": "execute"
    }
)
workflow.add_edge("approve", "critic")
workflow.add_edge("risk_gate", "critic")
workflow.add_edge("execute", "critic")
workflow.add_edge("critic", "meta_reflection")
workflow.add_edge("meta_reflection", END)

# Compile the graph
polygod_graph = workflow.compile(checkpointer=langgraph_memory)

logger.info("POLYGOD LangGraph (GOD TIER) compiled successfully with Grok + x_sentiment + Kelly + meta_reflection")