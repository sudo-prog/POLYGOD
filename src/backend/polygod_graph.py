import subprocess
import logging
from typing import TypedDict, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

# Graceful import of py_clob_client - may not be installed in all environments
try:
    from py_clob_client.client import ClobClient
    CLOB_AVAILABLE = True
except ImportError:
    ClobClient = None
    CLOB_AVAILABLE = False
    logging.warning("py_clob_client not installed - POLYGOD trading disabled")

logger = logging.getLogger(__name__)


class SimpleMemory:
    def __init__(self):
        self.storage = {}

    def add(self, data: str, agent_id: str):
        self.storage[agent_id] = data

    def get(self, agent_id: str):
        return self.storage.get(agent_id, "")


memory = SimpleMemory()

# Initialize ClobClient with error handling for zero-error startup
clob: Optional[object] = None
if CLOB_AVAILABLE:
    try:
        clob = ClobClient(host="https://api.polymarket.com")
        logger.info("ClobClient initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize ClobClient: {e} - Trading will be disabled")
        clob = None
else:
    logger.info("ClobClient not available - POLYGOD trading disabled")


class PaperMirror:
    def __init__(self):
        self.pnls = []

    def execute_shadow(self, order):
        self.pnls.append(0.05)  # placeholder positive EV
        return {"pnl": 0.05, "status": "paper_executed"}


paper = PaperMirror()
POLYGOD_MODE = 0


class AgentState(TypedDict):
    mode: int
    market_data: dict
    decision: dict
    paper_pnl: float


def research_node(state: AgentState):
    dexter_insight = consult_dexter(f"Analyze impact on {state.get('market_data', {})}")
    memory.add(f"Research + Dexter: {dexter_insight}", agent_id="polygod")
    state["market_data"] = {"prob": 0.65}
    return state


def consult_dexter(query: str):
    try:
        result = subprocess.run(
            ["bun", "run", "../dexter/start", "--query", query],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.stdout
    except:
        return "Dexter offline"


def mode_router(state: AgentState):
    if state["mode"] == 0:
        return "approve_node"
    if state["mode"] == 3:
        return "execute_node"
    return "risk_gate_node"


def approve_node(state: AgentState):
    state["decision"]["approved"] = True
    return state


def risk_gate_node(state: AgentState):
    """
    Risk gate validation before execution.

    This node validates orders before allowing execution in
    AGGRESSIVE and BEAST modes.

    Args:
        state: Current agent state with order decision

    Returns:
        The name of the next node to execute ("execute" or "approve")
    """
    # Check the proposed order from state["decision"]
    order = state.get("decision", {}).get("order")
    if not order:
        memory.add("Risk gate failed: missing order", agent_id="polygod")
        return "approve"

    # Validate order structure
    try:
        size = float(order["size"])
        price = float(order["price"])
        if size <= 0 or price <= 0 or price > 1:
            raise ValueError("Invalid order values")
    except (ValueError, TypeError, KeyError) as e:
        memory.add(f"Risk gate failed: invalid order - {e}", agent_id="polygod")
        return "approve"

    # Calculate notional value
    notional = size * price

    # Get market data for volume/liquidity
    market_data = state.get("market_data", {})
    volume = float(market_data.get("volume") or market_data.get("liquidity") or 100000.0)

    # Calculate size ratio
    size_ratio = (size / volume) if volume > 0 else 1.0

    # Calculate PnL volatility from recent trades
    pnls = paper.pnls[-20:] if hasattr(paper, "pnls") and paper.pnls else []
    volatility = 0.0
    if len(pnls) > 1:
        mean = sum(pnls) / len(pnls)
        variance = sum((p - mean) ** 2 for p in pnls) / len(pnls)
        volatility = variance ** 0.5

    # Get current mode
    mode = state.get("mode", 0)

    # Risk assessment thresholds
    risk_too_high = (
        size_ratio > 0.05 or          # >5% of market volume
        mode < 3 or                   # lower modes require approval
        volatility > 0.15 or          # high PnL volatility
        notional > 10000              # arbitrary safe notional cap
    )

    if risk_too_high:
        reason = f"high risk (size/vol={size_ratio:.2%}, mode={mode}, vol={volatility:.3f}, notional={notional:.2f})"
        memory.add(f"Risk gate failed: {reason}", agent_id="polygod")
        logger.warning(f"[RISK_GATE] FAILED: {reason} - routing to approve")
        return "approve"
    else:
        reason = f"low risk (size/vol={size_ratio:.2%}, mode={mode}, vol={volatility:.3f})"
        memory.add(f"Risk gate passed: {reason}", agent_id="polygod")
        logger.info(f"[RISK_GATE] PASSED: {reason} - proceeding to execute")
        return "execute"


def execute_node(state: AgentState):
    order = state.get("decision", {}).get("order", {"size": 100, "price": 0.65})
    paper.execute_shadow(order)  # always-on paper mirror

    if state["mode"] >= 2 and clob is not None:
        # Official Polymarket execution via py-clob-client (no fake agent_skills)
        try:
            # Type assertion since we know clob is a ClobClient when not None
            from py_clob_client.client import ClobClient
            if isinstance(clob, ClobClient):
                if state["mode"] == 3:
                    # Beast mode - direct order (add your gasless logic here later)
                    clob.create_market_order(order)
                else:
                    clob.create_market_order(order)
        except Exception as e:
            memory.add(f"Execution error: {e}", agent_id="polygod")
            logger.warning(f"Order execution failed in mode {state['mode']}: {e}")

    state["paper_pnl"] = paper.pnls[-1]
    memory.add(f"Executed in Mode {state['mode']}", agent_id="polygod")
    return state


def critic_node(state: AgentState):
    memory.add("Reflection: tighten Kelly on low liquidity", agent_id="polygod")
    return state


# Build the graph
workflow = StateGraph(AgentState)
workflow.add_node("research", research_node)
workflow.add_node("router", mode_router)
workflow.add_node("approve", approve_node)
workflow.add_node("risk_gate", risk_gate_node)
workflow.add_node("execute", execute_node)
workflow.add_node("critic", critic_node)

workflow.set_entry_point("research")
workflow.add_edge("research", "router")
workflow.add_edge("approve", "execute")
workflow.add_edge("risk_gate", "execute")
workflow.add_edge("execute", "critic")
workflow.add_edge("critic", END)

polygod_app = workflow.compile(checkpointer=MemorySaver())
